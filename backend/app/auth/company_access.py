"""Reusable company authorization without activating tenant-aware routes yet."""
from dataclasses import dataclass
from enum import Enum

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import Company, CompanyMembership, User


class CompanyPermission(str, Enum):
    READ = "read"
    EDIT = "edit"
    MANAGE = "manage"


ROLE_PERMISSIONS = {
    "LIETOTAJS": frozenset({CompanyPermission.READ, CompanyPermission.EDIT}),
    "VADITAJS": frozenset(
        {CompanyPermission.READ, CompanyPermission.EDIT, CompanyPermission.MANAGE}
    ),
}
ADMIN_PERMISSIONS = frozenset(CompanyPermission)


@dataclass(frozen=True)
class CompanyAccessContext:
    user: User
    company: Company
    membership: CompanyMembership | None
    role: str
    permissions: frozenset[CompanyPermission]
    system_access: bool


def authorize_company_access(
    db: Session,
    user: User,
    company_id: int,
    required_permission: CompanyPermission,
) -> CompanyAccessContext:
    """Resolve authorization exclusively from persisted identity and membership."""
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is not active",
        )

    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    if not company.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Company is not active",
        )

    if user.role == "ADMIN":
        return CompanyAccessContext(
            user=user,
            company=company,
            membership=None,
            role="ADMIN",
            permissions=ADMIN_PERMISSIONS,
            system_access=True,
        )

    membership = db.scalar(
        select(CompanyMembership).where(
            CompanyMembership.company_id == company.id,
            CompanyMembership.user_id == user.id,
            CompanyMembership.is_active.is_(True),
            CompanyMembership.approved_at.is_not(None),
        )
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active approved company membership is required",
        )

    permissions = ROLE_PERMISSIONS.get(membership.role, frozenset())
    if required_permission not in permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Company permission is required",
        )
    return CompanyAccessContext(
        user=user,
        company=company,
        membership=membership,
        role=membership.role,
        permissions=permissions,
        system_access=False,
    )


def company_permission_dependency(required_permission: CompanyPermission):
    def dependency(
        company_id: int,
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user),
    ) -> CompanyAccessContext:
        return authorize_company_access(db, user, company_id, required_permission)

    dependency.__name__ = f"require_company_{required_permission.value}_access"
    return dependency


require_company_read_access = company_permission_dependency(CompanyPermission.READ)
require_company_edit_access = company_permission_dependency(CompanyPermission.EDIT)
require_company_manager_access = company_permission_dependency(CompanyPermission.MANAGE)


def require_global_admin_access(user: User = Depends(get_current_user)) -> User:
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account is not active")
    if user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Global administrator permission is required",
        )
    return user
