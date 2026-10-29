from datetime import datetime, timezone

from app.auth.security import hash_password
from app.models import Company, CompanyJoinRequest, CompanyMembership, User


NOW = datetime.now(timezone.utc)


def auth_headers(client, email, password):
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def setup_companies(fresh_database):
    with fresh_database() as db:
        manager = User(name="Manager", email="manager@test.lv", password_hash=hash_password("Manager123!"))
        applicant = User(name="Applicant", email="applicant@test.lv", password_hash=hash_password("Applicant123!"))
        other = User(name="Other", email="other@test.lv", password_hash=hash_password("Other123!"))
        first = Company(name="First company", slug="first-company")
        second = Company(name="Second company", slug="second-company")
        inactive = Company(name="Inactive company", slug="inactive-company", is_active=False)
        db.add_all([manager, applicant, other, first, second, inactive])
        db.flush()
        db.add(CompanyMembership(company_id=first.id, user_id=manager.id, role="VADITAJS",
                                 approved_at=NOW, approved_by_id=manager.id))
        db.commit()
        return first.id, second.id, inactive.id, manager.id, applicant.id, other.id


def test_public_list_and_registration_create_only_pending_request(client, fresh_database):
    first_id, _, inactive_id, _, _, _ = setup_companies(fresh_database)
    response = client.get("/api/companies/public")
    assert response.status_code == 200
    assert [item["name"] for item in response.json()] == ["First company", "Second company"]
    assert set(response.json()[0]) == {"id", "name", "slug"}

    payload = {
        "name": "New User", "email": "new@test.lv", "companyId": first_id,
        "password": "Password123!", "passwordConfirmation": "Password123!",
    }
    assert client.post("/api/auth/register", json={
        **payload, "role": "ADMIN", "status": "APPROVED",
    }).status_code == 422
    registered = client.post("/api/auth/register", json=payload)
    assert registered.status_code == 201
    assert registered.json()["user"]["role"] == "USER"
    headers = {"Authorization": f"Bearer {registered.json()['accessToken']}"}
    assert client.get(f"/api/companies/{first_id}/items", headers=headers).status_code == 403

    with fresh_database() as db:
        user = db.query(User).filter_by(email="new@test.lv").one()
        request = db.query(CompanyJoinRequest).filter_by(user_id=user.id).one()
        assert request.company_id == first_id and request.status == "PENDING"
        assert db.query(CompanyMembership).filter_by(user_id=user.id).count() == 0

    assert client.post("/api/auth/register", json=payload).status_code == 409
    payload.update(email="invalid-company@test.lv", companyId=999999)
    assert client.post("/api/auth/register", json=payload).status_code == 404
    payload.update(email="inactive-company@test.lv", companyId=inactive_id)
    assert client.post("/api/auth/register", json=payload).status_code == 409


def test_mine_history_duplicate_pending_and_reapplication(client, fresh_database):
    first_id, second_id, _, _, applicant_id, _ = setup_companies(fresh_database)
    with fresh_database() as db:
        admin = db.query(User).filter_by(email="admin@test.lv").one()
        db.add(CompanyMembership(company_id=first_id, user_id=applicant_id, role="LIETOTAJS",
                                 approved_at=NOW, approved_by_id=admin.id))
        db.add(CompanyJoinRequest(company_id=first_id, user_id=applicant_id, status="APPROVED",
                                  reviewed_at=NOW, reviewed_by_id=admin.id))
        db.add(CompanyJoinRequest(company_id=second_id, user_id=applicant_id, status="REJECTED",
                                  reviewed_at=NOW, reviewed_by_id=admin.id, rejection_reason="Try later"))
        db.commit()
    headers = auth_headers(client, "applicant@test.lv", "Applicant123!")
    mine = client.get("/api/companies/mine", headers=headers)
    assert mine.status_code == 200
    assert [(item["id"], item["role"]) for item in mine.json()] == [(first_id, "LIETOTAJS")]
    history = client.get("/api/companies/my-requests", headers=headers)
    assert history.status_code == 200
    assert {item["status"] for item in history.json()} == {"APPROVED", "REJECTED"}
    assert all("reviewedById" not in item for item in history.json())

    created = client.post(f"/api/companies/{second_id}/join-requests", headers=headers)
    assert created.status_code == 201 and created.json()["status"] == "PENDING"
    assert client.post(f"/api/companies/{second_id}/join-requests", headers=headers).status_code == 409
    assert client.post(f"/api/companies/{first_id}/join-requests", headers=headers).status_code == 409


def test_manager_approval_rejection_and_company_isolation(client, fresh_database):
    first_id, second_id, _, _, applicant_id, other_id = setup_companies(fresh_database)
    with fresh_database() as db:
        first_request = CompanyJoinRequest(company_id=first_id, user_id=applicant_id)
        second_request = CompanyJoinRequest(company_id=second_id, user_id=other_id)
        db.add_all([first_request, second_request])
        db.commit()
        first_request_id, second_request_id = first_request.id, second_request.id
    manager_headers = auth_headers(client, "manager@test.lv", "Manager123!")
    applicant_headers = auth_headers(client, "applicant@test.lv", "Applicant123!")
    assert client.get(f"/api/companies/{first_id}/join-requests", headers=applicant_headers).status_code == 403
    queue = client.get(f"/api/companies/{first_id}/join-requests?status=PENDING", headers=manager_headers)
    assert queue.status_code == 200 and [item["id"] for item in queue.json()] == [first_request_id]
    assert client.post(
        f"/api/companies/{second_id}/join-requests/{second_request_id}/approve", headers=manager_headers
    ).status_code == 403

    approved = client.post(
        f"/api/companies/{first_id}/join-requests/{first_request_id}/approve", headers=manager_headers
    )
    assert approved.status_code == 200 and approved.json()["role"] == "LIETOTAJS"
    assert client.post(
        f"/api/companies/{first_id}/join-requests/{first_request_id}/approve", headers=manager_headers
    ).status_code == 409
    assert client.get(f"/api/companies/{first_id}/items", headers=applicant_headers).status_code == 200

    with fresh_database() as db:
        replacement = CompanyJoinRequest(company_id=first_id, user_id=other_id)
        db.add(replacement)
        db.commit()
        replacement_id = replacement.id
    rejected = client.post(
        f"/api/companies/{first_id}/join-requests/{replacement_id}/reject",
        headers=manager_headers, json={"reason": "No vacancy"},
    )
    assert rejected.status_code == 200 and rejected.json()["status"] == "REJECTED"
    with fresh_database() as db:
        assert db.query(CompanyMembership).filter_by(company_id=first_id, user_id=other_id).count() == 0


def test_membership_management_restrictions_and_revocation(client, fresh_database, admin_headers):
    first_id, second_id, _, _, applicant_id, _ = setup_companies(fresh_database)
    with fresh_database() as db:
        admin = db.query(User).filter_by(email="admin@test.lv").one()
        member = CompanyMembership(company_id=first_id, user_id=applicant_id, role="LIETOTAJS",
                                   approved_at=NOW, approved_by_id=admin.id)
        db.add(member)
        db.commit()
        member_id = member.id
    manager_headers = auth_headers(client, "manager@test.lv", "Manager123!")
    member_headers = auth_headers(client, "applicant@test.lv", "Applicant123!")
    members = client.get(f"/api/companies/{first_id}/members", headers=manager_headers)
    manager_membership = next(item for item in members.json() if item["role"] == "VADITAJS")
    assert client.patch(
        f"/api/companies/{first_id}/members/{manager_membership['id']}",
        headers=manager_headers, json={"role": "LIETOTAJS"},
    ).status_code == 409
    assert client.patch(
        f"/api/companies/{first_id}/members/{manager_membership['id']}",
        headers=admin_headers, json={"role": "LIETOTAJS"},
    ).status_code == 409
    assert client.patch(
        f"/api/companies/{first_id}/members/{member_id}",
        headers=manager_headers, json={"role": "ADMIN"},
    ).status_code == 422
    assert client.post(
        f"/api/companies/{second_id}/members/{member_id}/revoke", headers=manager_headers
    ).status_code == 403
    revoked = client.post(
        f"/api/companies/{first_id}/members/{member_id}/revoke", headers=manager_headers
    )
    assert revoked.status_code == 200 and revoked.json()["isActive"] is False
    assert client.get(f"/api/companies/{first_id}/items", headers=member_headers).status_code == 403


def test_global_admin_company_creation_and_review(client, fresh_database, admin_headers):
    first_id, _, _, _, applicant_id, _ = setup_companies(fresh_database)
    created = client.post("/api/admin/companies", headers=admin_headers, json={
        "name": "Admin-created company", "slug": "admin-created-company",
        "initialManagerUserId": applicant_id,
    })
    assert created.status_code == 201
    company_id = created.json()["id"]
    with fresh_database() as db:
        created_membership_id = db.query(CompanyMembership).filter_by(company_id=company_id).one().id
    assert client.patch(
        f"/api/companies/{first_id}/members/{created_membership_id}",
        headers=admin_headers, json={"role": "LIETOTAJS"},
    ).status_code == 404
    assert client.post("/api/admin/companies", headers=admin_headers, json={
        "name": "Admin-created company", "slug": "another-slug",
        "initialManagerUserId": applicant_id,
    }).status_code == 409
    with fresh_database() as db:
        user = db.query(User).filter_by(email="other@test.lv").one()
        request = CompanyJoinRequest(company_id=first_id, user_id=user.id)
        db.add(request)
        db.commit()
        request_id = request.id
    review = client.get("/api/admin/join-requests?status=PENDING", headers=admin_headers)
    assert review.status_code == 200 and request_id in {item["id"] for item in review.json()}
    approved = client.post(
        f"/api/companies/{first_id}/join-requests/{request_id}/approve", headers=admin_headers
    )
    assert approved.status_code == 200
    admin_mine = client.get("/api/companies/mine", headers=admin_headers)
    assert admin_mine.status_code == 200
    assert company_id in {item["id"] for item in admin_mine.json()}
