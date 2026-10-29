from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Company, CompanyJoinRequest, CompanyMembership, User
from app.schemas import CompanyJoinRequestOut, CompanyMembershipOut, CompanyOut, RegisterIn


def company(name, slug):
    return Company(name=name, slug=slug)


def test_company_slug_is_unique_and_output_schema(test_engine):
    with Session(test_engine) as session:
        first = company("Shared name", "first-company")
        second = company("Shared name", "second-company")
        session.add_all([first, second])
        session.commit()

        output = CompanyOut.model_validate(first)
        assert output.slug == "first-company"
        assert output.is_active is True
        assert output.created_at is not None and output.updated_at is not None

        session.add(company("Duplicate slug", "first-company"))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_membership_uniqueness_roles_and_multiple_companies(fresh_database, test_engine):
    with fresh_database() as session:
        user = session.query(User).filter_by(email="user@test.lv").one()
        admin = session.query(User).filter_by(email="admin@test.lv").one()
        first = company("First", "first")
        second = company("Second", "second")
        session.add_all([first, second])
        session.flush()
        first_membership = CompanyMembership(
            company_id=first.id,
            user_id=user.id,
            role="LIETOTAJS",
            approved_at=datetime.now(timezone.utc),
            approved_by_id=admin.id,
        )
        second_membership = CompanyMembership(
            company_id=second.id,
            user_id=user.id,
            role="VADITAJS",
            approved_at=datetime.now(timezone.utc),
            approved_by_id=admin.id,
        )
        session.add_all([first_membership, second_membership])
        session.commit()

        assert {item.company_id for item in user.company_memberships} == {first.id, second.id}
        assert first_membership.approved_by is admin
        assert CompanyMembershipOut.model_validate(second_membership).role == "VADITAJS"

        session.add(CompanyMembership(company_id=first.id, user_id=user.id, role="LIETOTAJS"))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add(CompanyMembership(company_id=second.id, user_id=admin.id, role="ADMIN"))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_join_request_pending_uniqueness_status_and_history(fresh_database, test_engine):
    with fresh_database() as session:
        user = session.query(User).filter_by(email="user@test.lv").one()
        admin = session.query(User).filter_by(email="admin@test.lv").one()
        target = company("Requests", "requests")
        session.add(target)
        session.flush()

        pending = CompanyJoinRequest(company_id=target.id, user_id=user.id)
        session.add(pending)
        session.commit()
        assert pending.status == "PENDING"

        session.add(CompanyJoinRequest(company_id=target.id, user_id=user.id))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        pending.status = "REJECTED"
        pending.reviewed_at = datetime.now(timezone.utc)
        pending.reviewed_by_id = admin.id
        pending.rejection_reason = "Not yet"
        replacement = CompanyJoinRequest(company_id=target.id, user_id=user.id)
        approved_history = CompanyJoinRequest(
            company_id=target.id,
            user_id=user.id,
            status="APPROVED",
            reviewed_at=datetime.now(timezone.utc),
            reviewed_by_id=admin.id,
        )
        session.add_all([replacement, approved_history])
        session.commit()

        requests = session.query(CompanyJoinRequest).order_by(CompanyJoinRequest.id).all()
        assert [request.status for request in requests] == ["REJECTED", "PENDING", "APPROVED"]
        assert requests[0].reviewed_by is admin
        assert CompanyJoinRequestOut.model_validate(requests[0]).rejection_reason == "Not yet"

        session.add(CompanyJoinRequest(company_id=target.id, user_id=admin.id, status="CANCELLED"))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


@pytest.mark.parametrize(
    "model",
    [
        lambda user_id: CompanyMembership(company_id=999999, user_id=user_id, role="LIETOTAJS"),
        lambda user_id: CompanyMembership(company_id=1, user_id=999999, role="LIETOTAJS"),
        lambda user_id: CompanyMembership(
            company_id=1, user_id=user_id, role="LIETOTAJS", approved_by_id=999999
        ),
        lambda user_id: CompanyMembership(
            company_id=1, user_id=user_id, role="LIETOTAJS", revoked_by_id=999999
        ),
        lambda user_id: CompanyJoinRequest(company_id=999999, user_id=user_id),
        lambda user_id: CompanyJoinRequest(company_id=1, user_id=999999),
        lambda user_id: CompanyJoinRequest(company_id=1, user_id=user_id, reviewed_by_id=999999),
    ],
)
def test_company_foreign_keys_are_enforced(fresh_database, test_engine, model):
    with fresh_database() as session:
        user = session.query(User).filter_by(email="user@test.lv").one()
        target = company("FK company", "fk-company")
        session.add(target)
        session.commit()
        session.add(model(user.id))
        with pytest.raises(IntegrityError):
            session.commit()


def test_public_registration_schema_has_no_company_privilege_fields():
    assert {"role", "status", "is_active", "approved_by_id", "reviewed_by_id"}.isdisjoint(
        RegisterIn.model_fields
    )
