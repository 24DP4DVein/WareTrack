from datetime import datetime, timezone
import inspect

import pytest
from fastapi import HTTPException

from app.auth.company_access import (
    CompanyPermission,
    authorize_company_access,
    require_company_edit_access,
    require_company_manager_access,
    require_company_read_access,
    require_global_admin_access,
)
from app.auth.dependencies import get_current_user
from app.models import Company, CompanyJoinRequest, CompanyMembership, User


def add_company(session, name, slug, *, active=True):
    company = Company(name=name, slug=slug, is_active=active)
    session.add(company)
    session.flush()
    return company


def approve(session, company, user, role, *, active=True):
    membership = CompanyMembership(
        company_id=company.id,
        user_id=user.id,
        role=role,
        is_active=active,
        approved_at=datetime.now(timezone.utc),
    )
    session.add(membership)
    session.flush()
    return membership


def assert_denied(status_code, callable_, *args, **kwargs):
    with pytest.raises(HTTPException) as exc:
        callable_(*args, **kwargs)
    assert exc.value.status_code == status_code


def test_no_membership_and_pending_or_rejected_requests_grant_no_access(fresh_database):
    with fresh_database() as session:
        user = session.query(User).filter_by(email="user@test.lv").one()
        company = add_company(session, "Requests only", "requests-only")
        session.add_all([
            CompanyJoinRequest(company_id=company.id, user_id=user.id, status="PENDING"),
            CompanyJoinRequest(company_id=company.id, user_id=user.id, status="REJECTED"),
            CompanyMembership(
                company_id=company.id,
                user_id=user.id,
                role="LIETOTAJS",
                is_active=True,
                approved_at=None,
            ),
        ])
        session.commit()

        assert_denied(
            403, authorize_company_access, session, user, company.id, CompanyPermission.READ
        )


def test_multiple_company_memberships_apply_their_own_roles(fresh_database):
    with fresh_database() as session:
        user = session.query(User).filter_by(email="user@test.lv").one()
        first = add_company(session, "First", "access-first")
        second = add_company(session, "Second", "access-second")
        first_membership = approve(session, first, user, "LIETOTAJS")
        second_membership = approve(session, second, user, "VADITAJS")
        session.commit()

        read = require_company_read_access(company_id=first.id, db=session, user=user)
        edit = require_company_edit_access(company_id=first.id, db=session, user=user)
        assert read.membership is first_membership
        assert edit.role == "LIETOTAJS"
        assert read.system_access is False
        assert_denied(
            403,
            require_company_manager_access,
            company_id=first.id,
            db=session,
            user=user,
        )

        manager = require_company_manager_access(
            company_id=second.id, db=session, user=user
        )
        assert manager.membership is second_membership
        assert manager.role == "VADITAJS"


def test_inactive_company_membership_and_user_are_denied(fresh_database):
    with fresh_database() as session:
        user = session.query(User).filter_by(email="user@test.lv").one()
        inactive_company = add_company(session, "Inactive company", "inactive-company", active=False)
        active_company = add_company(session, "Inactive membership", "inactive-membership")
        approve(session, inactive_company, user, "VADITAJS")
        approve(session, active_company, user, "VADITAJS", active=False)
        session.commit()

        assert_denied(
            403,
            authorize_company_access,
            session,
            user,
            inactive_company.id,
            CompanyPermission.READ,
        )
        assert_denied(
            403,
            authorize_company_access,
            session,
            user,
            active_company.id,
            CompanyPermission.READ,
        )
        user.is_active = False
        session.commit()
        assert_denied(
            401,
            authorize_company_access,
            session,
            user,
            active_company.id,
            CompanyPermission.READ,
        )


def test_global_admin_has_explicit_system_access_without_membership(fresh_database):
    with fresh_database() as session:
        admin = session.query(User).filter_by(email="admin@test.lv").one()
        user = session.query(User).filter_by(email="user@test.lv").one()
        company = add_company(session, "Admin target", "admin-target")
        session.commit()

        context = authorize_company_access(
            session, admin, company.id, CompanyPermission.MANAGE
        )
        assert context.system_access is True
        assert context.membership is None
        assert context.role == "ADMIN"
        assert require_global_admin_access(admin) is admin
        assert_denied(403, require_global_admin_access, user)


def test_unknown_and_other_company_ids_do_not_authorize(fresh_database):
    with fresh_database() as session:
        user = session.query(User).filter_by(email="user@test.lv").one()
        allowed = add_company(session, "Allowed", "allowed")
        other = add_company(session, "Other", "other")
        approve(session, allowed, user, "VADITAJS")
        session.commit()

        assert authorize_company_access(
            session, user, allowed.id, CompanyPermission.READ
        ).company.id == allowed.id
        assert_denied(
            403, authorize_company_access, session, user, other.id, CompanyPermission.READ
        )
        assert_denied(
            404, authorize_company_access, session, user, 999999, CompanyPermission.READ
        )


def test_company_dependencies_chain_through_jwt_identity():
    for dependency in (
        require_company_read_access,
        require_company_edit_access,
        require_company_manager_access,
    ):
        user_parameter = inspect.signature(dependency).parameters["user"]
        assert user_parameter.default.dependency is get_current_user
    user_parameter = inspect.signature(require_global_admin_access).parameters["user"]
    assert user_parameter.default.dependency is get_current_user
