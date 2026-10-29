from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.company_access import (
    CompanyAccessContext,
    require_company_manager_access,
    require_global_admin_access,
)
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import Company, CompanyJoinRequest, CompanyMembership, Transfer, User
from app.schemas import (
    AdminCompanyCreate,
    AdminCompanyUpdate,
    CompanyOut,
    InitialManagerIn,
    JoinRequestRejectIn,
    ManagedJoinRequestOut,
    ManagedMembershipOut,
    MembershipRoleUpdate,
    MyCompanyOut,
    MyJoinRequestOut,
    PublicCompanyOut,
)
from app.services.activity import log_activity


router = APIRouter(prefix="/companies", tags=["Companies"])
admin_router = APIRouter(prefix="/admin", tags=["Company administration"])


def _request_output(request: CompanyJoinRequest) -> dict:
    return {
        "id": request.id,
        "company_id": request.company_id,
        "company_name": request.company.name,
        "user_id": request.user_id,
        "user_name": request.user.name,
        "user_email": request.user.email,
        "status": request.status,
        "requested_at": request.requested_at,
        "reviewed_at": request.reviewed_at,
        "rejection_reason": request.rejection_reason,
    }


def _membership_output(membership: CompanyMembership) -> dict:
    return {
        "id": membership.id,
        "company_id": membership.company_id,
        "user_id": membership.user_id,
        "user_name": membership.user.name,
        "user_email": membership.user.email,
        "role": membership.role,
        "is_active": membership.is_active,
        "approved_at": membership.approved_at,
        "revoked_at": membership.revoked_at,
    }


def _pending_request(db: Session, company_id: int, request_id: int) -> CompanyJoinRequest:
    request = db.scalar(
        select(CompanyJoinRequest).where(
            CompanyJoinRequest.id == request_id,
            CompanyJoinRequest.company_id == company_id,
        )
    )
    if request is None:
        raise HTTPException(404, "Join request not found")
    if request.status != "PENDING":
        raise HTTPException(409, "Join request has already been reviewed")
    return request


def _active_manager_count(db: Session, company_id: int) -> int:
    return db.scalar(
        select(func.count(CompanyMembership.id)).where(
            CompanyMembership.company_id == company_id,
            CompanyMembership.role == "VADITAJS",
            CompanyMembership.is_active.is_(True),
            CompanyMembership.approved_at.is_not(None),
        )
    ) or 0


@router.get("/public", response_model=list[PublicCompanyOut])
def public_companies(db: Session = Depends(get_db)):
    return db.scalars(
        select(Company).where(Company.is_active.is_(True)).order_by(func.lower(Company.name), Company.id)
    ).all()


@router.get("/mine", response_model=list[MyCompanyOut])
def my_companies(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role == "ADMIN":
        companies = db.scalars(
            select(Company).where(Company.is_active.is_(True)).order_by(func.lower(Company.name), Company.id)
        ).all()
        return [{"id": c.id, "name": c.name, "slug": c.slug, "role": "ADMIN"} for c in companies]

    memberships = db.scalars(
        select(CompanyMembership)
        .join(Company)
        .where(
            CompanyMembership.user_id == user.id,
            CompanyMembership.is_active.is_(True),
            CompanyMembership.approved_at.is_not(None),
            Company.is_active.is_(True),
        )
        .order_by(func.lower(Company.name), Company.id)
    ).all()
    return [
        {"id": m.company.id, "name": m.company.name, "slug": m.company.slug, "role": m.role}
        for m in memberships
    ]


@router.get("/my-requests", response_model=list[MyJoinRequestOut])
def my_requests(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    requests = db.scalars(
        select(CompanyJoinRequest)
        .where(CompanyJoinRequest.user_id == user.id)
        .order_by(CompanyJoinRequest.requested_at.desc(), CompanyJoinRequest.id.desc())
    ).all()
    return [
        {
            "id": request.id,
            "company_id": request.company_id,
            "company_name": request.company.name,
            "status": request.status,
            "requested_at": request.requested_at,
            "reviewed_at": request.reviewed_at,
            "rejection_reason": request.rejection_reason,
        }
        for request in requests
    ]


@router.post("/{company_id}/join-requests", response_model=MyJoinRequestOut, status_code=201)
def submit_join_request(
    company_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(404, "Company not found")
    if not company.is_active:
        raise HTTPException(409, "Company is not active")
    membership = db.scalar(
        select(CompanyMembership).where(
            CompanyMembership.company_id == company_id,
            CompanyMembership.user_id == user.id,
            CompanyMembership.is_active.is_(True),
            CompanyMembership.approved_at.is_not(None),
        )
    )
    if membership:
        raise HTTPException(409, "User already has active company membership")
    request = CompanyJoinRequest(company_id=company_id, user_id=user.id, status="PENDING")
    try:
        db.add(request)
        db.commit()
        db.refresh(request)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A pending join request already exists") from None
    return {
        "id": request.id,
        "company_id": request.company_id,
        "company_name": company.name,
        "status": request.status,
        "requested_at": request.requested_at,
        "reviewed_at": None,
        "rejection_reason": None,
    }


@router.get("/{company_id}/join-requests", response_model=list[ManagedJoinRequestOut])
def company_join_requests(
    company_id: int,
    status_filter: Literal["PENDING", "APPROVED", "REJECTED"] | None = Query(None, alias="status"),
    _: CompanyAccessContext = Depends(require_company_manager_access),
    db: Session = Depends(get_db),
):
    statement = select(CompanyJoinRequest).where(CompanyJoinRequest.company_id == company_id)
    if status_filter:
        statement = statement.where(CompanyJoinRequest.status == status_filter)
    if status_filter in (None, "PENDING"):
        statement = statement.order_by(CompanyJoinRequest.requested_at, CompanyJoinRequest.id)
    else:
        statement = statement.order_by(CompanyJoinRequest.requested_at.desc(), CompanyJoinRequest.id.desc())
    return [_request_output(item) for item in db.scalars(statement).all()]


@router.post("/{company_id}/join-requests/{request_id}/approve", response_model=ManagedMembershipOut)
def approve_join_request(
    company_id: int,
    request_id: int,
    access: CompanyAccessContext = Depends(require_company_manager_access),
    db: Session = Depends(get_db),
):
    request = _pending_request(db, company_id, request_id)
    if request.user_id == access.user.id:
        raise HTTPException(403, "Users cannot approve their own join requests")
    now = datetime.now(timezone.utc)
    result = db.execute(
        update(CompanyJoinRequest)
        .where(CompanyJoinRequest.id == request_id, CompanyJoinRequest.status == "PENDING")
        .values(status="APPROVED", reviewed_at=now, reviewed_by_id=access.user.id, rejection_reason=None)
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Join request has already been reviewed")
    membership = db.scalar(
        select(CompanyMembership).where(
            CompanyMembership.company_id == company_id,
            CompanyMembership.user_id == request.user_id,
        )
    )
    if membership is None:
        membership = CompanyMembership(company_id=company_id, user_id=request.user_id, role="LIETOTAJS")
        db.add(membership)
    membership.role = "LIETOTAJS"
    membership.is_active = True
    membership.approved_at = now
    membership.approved_by_id = access.user.id
    membership.revoked_at = None
    membership.revoked_by_id = None
    try:
        db.flush()
        log_activity(db, access.user, "approve", "company_join_request", request_id,
                     f"Approved join request for user {request.user_id}", company_id=company_id)
        db.commit()
        db.refresh(membership)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Join request approval conflicted with another update") from None
    return _membership_output(membership)


@router.post("/{company_id}/join-requests/{request_id}/reject", response_model=ManagedJoinRequestOut)
def reject_join_request(
    company_id: int,
    request_id: int,
    data: JoinRequestRejectIn,
    access: CompanyAccessContext = Depends(require_company_manager_access),
    db: Session = Depends(get_db),
):
    request = _pending_request(db, company_id, request_id)
    if request.user_id == access.user.id:
        raise HTTPException(403, "Users cannot review their own join requests")
    reason = data.reason.strip() if data.reason else None
    now = datetime.now(timezone.utc)
    result = db.execute(
        update(CompanyJoinRequest)
        .where(CompanyJoinRequest.id == request_id, CompanyJoinRequest.status == "PENDING")
        .values(status="REJECTED", reviewed_at=now, reviewed_by_id=access.user.id,
                rejection_reason=reason)
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Join request has already been reviewed")
    log_activity(db, access.user, "reject", "company_join_request", request_id,
                 f"Rejected join request for user {request.user_id}", company_id=company_id)
    db.commit()
    reviewed = db.get(CompanyJoinRequest, request_id)
    return _request_output(reviewed)


@router.get("/{company_id}/members", response_model=list[ManagedMembershipOut])
def company_members(
    company_id: int,
    _: CompanyAccessContext = Depends(require_company_manager_access),
    db: Session = Depends(get_db),
):
    memberships = db.scalars(
        select(CompanyMembership)
        .join(User, CompanyMembership.user_id == User.id)
        .where(CompanyMembership.company_id == company_id)
        .order_by(CompanyMembership.is_active.desc(), func.lower(User.name), CompanyMembership.id)
    ).all()
    return [_membership_output(item) for item in memberships]


@router.patch("/{company_id}/members/{membership_id}", response_model=ManagedMembershipOut)
def update_membership(
    company_id: int,
    membership_id: int,
    data: MembershipRoleUpdate,
    access: CompanyAccessContext = Depends(require_company_manager_access),
    db: Session = Depends(get_db),
):
    membership = db.scalar(select(CompanyMembership).where(
        CompanyMembership.id == membership_id, CompanyMembership.company_id == company_id
    ))
    if membership is None:
        raise HTTPException(404, "Membership not found")
    if not membership.is_active:
        raise HTTPException(409, "Inactive membership cannot be changed")
    if membership.user_id == access.user.id and membership.role == "VADITAJS" and data.role != "VADITAJS":
        raise HTTPException(409, "Managers cannot demote themselves")
    if membership.role == "VADITAJS" and data.role != "VADITAJS" and _active_manager_count(db, company_id) <= 1:
        raise HTTPException(409, "The last active manager cannot be demoted")
    old_role = membership.role
    membership.role = data.role
    log_activity(db, access.user, "update_role", "company_membership", membership.id,
                 f"Changed membership role from {old_role} to {data.role}", company_id=company_id)
    db.commit()
    db.refresh(membership)
    return _membership_output(membership)


@router.post("/{company_id}/members/{membership_id}/revoke", response_model=ManagedMembershipOut)
def revoke_membership(
    company_id: int,
    membership_id: int,
    access: CompanyAccessContext = Depends(require_company_manager_access),
    db: Session = Depends(get_db),
):
    membership = db.scalar(select(CompanyMembership).where(
        CompanyMembership.id == membership_id, CompanyMembership.company_id == company_id
    ))
    if membership is None:
        raise HTTPException(404, "Membership not found")
    if not membership.is_active:
        raise HTTPException(409, "Membership has already been revoked")
    if membership.user_id == access.user.id:
        raise HTTPException(409, "Managers cannot revoke their own membership")
    if membership.role == "VADITAJS" and _active_manager_count(db, company_id) <= 1:
        raise HTTPException(409, "The last active manager cannot be revoked")
    now = datetime.now(timezone.utc)
    membership.is_active = False
    membership.revoked_at = now
    membership.revoked_by_id = access.user.id
    log_activity(db, access.user, "revoke", "company_membership", membership.id,
                 f"Revoked membership for user {membership.user_id}", company_id=company_id)
    db.commit()
    db.refresh(membership)
    return _membership_output(membership)


@admin_router.get("/companies", response_model=list[CompanyOut])
def admin_companies(_: User = Depends(require_global_admin_access), db: Session = Depends(get_db)):
    return db.scalars(select(Company).order_by(func.lower(Company.name), Company.id)).all()


@admin_router.post("/companies", response_model=CompanyOut, status_code=status.HTTP_201_CREATED)
def create_company(
    data: AdminCompanyCreate,
    admin: User = Depends(require_global_admin_access),
    db: Session = Depends(get_db),
):
    name = data.name.strip()
    if db.scalar(select(Company.id).where(func.lower(Company.name) == name.lower())):
        raise HTTPException(409, "Company name already exists")
    if db.scalar(select(Company.id).where(func.lower(Company.slug) == data.slug.lower())):
        raise HTTPException(409, "Company slug already exists")
    manager = db.get(User, data.initial_manager_user_id)
    if manager is None or not manager.is_active:
        raise HTTPException(404, "Active initial manager user not found")
    company = Company(name=name, slug=data.slug.lower())
    now = datetime.now(timezone.utc)
    try:
        db.add(company)
        db.flush()
        db.add(CompanyMembership(company_id=company.id, user_id=manager.id, role="VADITAJS",
                                 approved_at=now, approved_by_id=admin.id))
        log_activity(db, admin, "create", "company", company.id,
                     f"Created company {company.name} and appointed initial manager", company_id=company.id)
        db.commit()
        db.refresh(company)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Company could not be created") from None
    return company


@admin_router.patch("/companies/{company_id}", response_model=CompanyOut)
def update_company(
    company_id: int,
    data: AdminCompanyUpdate,
    admin: User = Depends(require_global_admin_access),
    db: Session = Depends(get_db),
):
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(404, "Company not found")
    if data.name is not None:
        name = data.name.strip()
        duplicate = db.scalar(select(Company.id).where(
            Company.id != company_id, func.lower(Company.name) == name.lower()
        ))
        if duplicate:
            raise HTTPException(409, "Company name already exists")
        company.name = name
    if data.is_active is False and company.is_active:
        unresolved_transfers = db.scalar(select(func.count(Transfer.id)).where(
            Transfer.company_id == company_id, Transfer.status.in_(("pending", "in-transit"))
        )) or 0
        pending_requests = db.scalar(select(func.count(CompanyJoinRequest.id)).where(
            CompanyJoinRequest.company_id == company_id, CompanyJoinRequest.status == "PENDING"
        )) or 0
        if unresolved_transfers or pending_requests:
            raise HTTPException(409, "Company has unresolved transfers or join requests")
    if data.is_active is not None:
        company.is_active = data.is_active
    log_activity(db, admin, "update", "company", company.id,
                 f"Updated company {company.name}", company_id=company.id)
    db.commit()
    db.refresh(company)
    return company


@admin_router.post("/companies/{company_id}/initial-manager", response_model=ManagedMembershipOut)
def appoint_initial_manager(
    company_id: int,
    data: InitialManagerIn,
    admin: User = Depends(require_global_admin_access),
    db: Session = Depends(get_db),
):
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(404, "Company not found")
    if _active_manager_count(db, company_id):
        raise HTTPException(409, "Company already has an active manager")
    user = db.get(User, data.user_id)
    if user is None or not user.is_active:
        raise HTTPException(404, "Active manager user not found")
    membership = db.scalar(select(CompanyMembership).where(
        CompanyMembership.company_id == company_id, CompanyMembership.user_id == user.id
    ))
    now = datetime.now(timezone.utc)
    if membership is None:
        membership = CompanyMembership(company_id=company_id, user_id=user.id, role="VADITAJS")
        db.add(membership)
    membership.role = "VADITAJS"
    membership.is_active = True
    membership.approved_at = now
    membership.approved_by_id = admin.id
    membership.revoked_at = None
    membership.revoked_by_id = None
    db.flush()
    log_activity(db, admin, "appoint_manager", "company_membership", membership.id,
                 f"Appointed initial manager user {user.id}", company_id=company_id)
    db.commit()
    db.refresh(membership)
    return _membership_output(membership)


@admin_router.get("/join-requests", response_model=list[ManagedJoinRequestOut])
def admin_join_requests(
    status_filter: Literal["PENDING", "APPROVED", "REJECTED"] | None = Query(None, alias="status"),
    _: User = Depends(require_global_admin_access),
    db: Session = Depends(get_db),
):
    statement = select(CompanyJoinRequest)
    if status_filter:
        statement = statement.where(CompanyJoinRequest.status == status_filter)
    statement = statement.order_by(CompanyJoinRequest.requested_at, CompanyJoinRequest.id)
    return [_request_output(item) for item in db.scalars(statement).all()]
