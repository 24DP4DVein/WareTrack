import pytest

from app.models import Role


def test_valid_login(client):
    response = client.post("/api/auth/login", json={"email": "user@test.lv", "password": "User123!"})
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "VADITAJS"


def test_session_role_matches_database_user(client, user_headers):
    response = client.get("/api/auth/me", headers=user_headers)
    assert response.status_code == 200
    assert response.json()["role"] == "VADITAJS"


def test_invalid_login(client):
    response = client.post("/api/auth/login", json={"email": "user@test.lv", "password": "wrong"})
    assert response.status_code == 401


def test_protected_endpoint(client):
    assert client.get("/api/suppliers").status_code == 401


def test_invalid_token_is_rejected(client):
    response = client.get(
        "/api/dashboard",
        headers={"Authorization": "Bearer definitely-not-a-jwt"},
    )
    assert response.status_code == 401


def test_role_permissions(client, user_headers, admin_headers):
    payload = {"name": "Jauna kategorija", "description": "Apraksts", "icon": "Package", "color": "blue"}
    assert client.post("/api/categories", json=payload, headers=user_headers).status_code == 201
    assert client.post("/api/categories", json={**payload, "name": "Otra kategorija"}, headers=admin_headers).status_code == 201


def test_manager_can_manage_suppliers_and_locations(client, user_headers):
    supplier = {"name": "Jauns piegādātājs", "contactPerson": "Anna Liepa", "email": "new@supplier.lv",
                "phone": "+371 20000001", "address": "Rīga, Latvija", "category": "Testi", "paymentTerms": "net30"}
    location = {"code": "RIG-C01", "name": "Rīga C1", "capacity": 100}
    created_supplier = client.post("/api/suppliers", json=supplier, headers=user_headers)
    created_location = client.post("/api/locations", json=location, headers=user_headers)
    assert created_supplier.status_code == 201
    assert created_location.status_code == 201
    supplier_id = created_supplier.json()["id"]
    location_id = created_location.json()["id"]
    assert client.put(f"/api/suppliers/{supplier_id}", json={**supplier, "name": "Atjaunots piegādātājs"}, headers=user_headers).status_code == 200
    assert client.put(f"/api/locations/{location_id}", json={**location, "name": "Rīga C2"}, headers=user_headers).status_code == 200
    assert client.delete(f"/api/suppliers/{supplier_id}", headers=user_headers).status_code == 204
    assert client.delete(f"/api/locations/{location_id}", headers=user_headers).status_code == 204


    def test_admin_can_use_operational_endpoints(client, admin_headers):
        item = {"name": "Administratora prece", "sku": "ADM-001", "categoryId": 1, "locationId": 1,
            "stock": 1, "minStock": 0, "price": 1, "description": ""}
        assert client.post("/api/items", json=item, headers=admin_headers).status_code == 201
        assert client.post("/api/transfers", json={"itemId": 1, "sourceLocationId": 1,
           "destinationLocationId": 2, "quantity": 1}, headers=admin_headers).status_code == 201


@pytest.mark.parametrize("submitted_role", ["VADITAJS", "ADMIN"])
def test_public_registration_defaults_to_read_only_and_ignores_submitted_role(client, submitted_role):
    response = client.post("/api/auth/register", json={
        "name": "Jauns lietotājs",
        "email": "new@test.lv",
        "password": "Secure123!",
        "passwordConfirmation": "Secure123!",
        "role": submitted_role,
    })
    assert response.status_code == 201
    assert response.json()["user"]["role"] == "LIETOTAJS"


def test_role_enum_has_exactly_three_roles():
    assert {role.value for role in Role} == {"LIETOTAJS", "VADITAJS", "ADMIN"}


def test_read_only_user_can_read_but_cannot_mutate(client, viewer_headers):
    for path in ("/api/dashboard", "/api/reports", "/api/activity", "/api/items", "/api/categories",
                 "/api/suppliers", "/api/locations", "/api/transfers", "/api/auth/me"):
        assert client.get(path, headers=viewer_headers).status_code == 200

    item = {"name": "Jauna prece", "sku": "NEW-002", "categoryId": 1, "locationId": 1,
            "stock": 1, "minStock": 0, "price": 1, "description": ""}
    category = {"name": "Jauna kategorija", "description": "", "icon": "Package", "color": "blue"}
    supplier = {"name": "Jauns piegādātājs", "contactPerson": "Anna Liepa", "email": "new@supplier.lv",
                "phone": "+371 20000001", "address": "Rīga, Latvija", "category": "Testi", "paymentTerms": "net30"}
    location = {"code": "RIG-C01", "name": "Rīga C1", "capacity": 100}
    transfer = {"itemId": 1, "sourceLocationId": 1, "destinationLocationId": 2, "quantity": 1}
    assert client.post("/api/items", json=item, headers=viewer_headers).status_code == 403
    assert client.put("/api/items/1", json=item, headers=viewer_headers).status_code == 403
    assert client.delete("/api/items/1", headers=viewer_headers).status_code == 403
    assert client.post("/api/categories", json=category, headers=viewer_headers).status_code == 403
    assert client.put("/api/categories/1", json=category, headers=viewer_headers).status_code == 403
    assert client.delete("/api/categories/1", headers=viewer_headers).status_code == 403
    assert client.post("/api/suppliers", json=supplier, headers=viewer_headers).status_code == 403
    assert client.put("/api/suppliers/1", json=supplier, headers=viewer_headers).status_code == 403
    assert client.delete("/api/suppliers/1", headers=viewer_headers).status_code == 403
    assert client.post("/api/locations", json=location, headers=viewer_headers).status_code == 403
    assert client.put("/api/locations/1", json=location, headers=viewer_headers).status_code == 403
    assert client.delete("/api/locations/1", headers=viewer_headers).status_code == 403
    assert client.post("/api/transfers", json=transfer, headers=viewer_headers).status_code == 403
    assert client.patch("/api/transfers/1", json={"status": "cancelled"}, headers=viewer_headers).status_code == 403
    assert client.delete("/api/transfers/1", headers=viewer_headers).status_code == 403
    assert client.get("/api/users", headers=viewer_headers).status_code == 403
    assert client.patch("/api/users/2", json={"role": "ADMIN"}, headers=viewer_headers).status_code == 403


def test_manager_cannot_manage_users(client, user_headers):
    assert client.get("/api/users", headers=user_headers).status_code == 403
    assert client.patch("/api/users/3", json={"role": "ADMIN"}, headers=user_headers).status_code == 403
    assert client.post("/api/users", json={"name": "New", "email": "new@test.lv", "password": "Secure123!"}, headers=user_headers).status_code == 403


def test_admin_can_create_users_with_default_or_explicit_role(client, admin_headers):
    default_user = client.post("/api/users", json={
        "name": "New Viewer", "email": "new-viewer@test.lv", "password": "Secure123!",
    }, headers=admin_headers)
    manager = client.post("/api/users", json={
        "name": "New Manager", "email": "new-manager@test.lv", "password": "Secure123!", "role": "VADITAJS",
    }, headers=admin_headers)
    assert default_user.status_code == 201
    assert default_user.json()["role"] == "LIETOTAJS"
    assert manager.status_code == 201
    assert manager.json()["role"] == "VADITAJS"
    activity = client.get("/api/activity", headers=admin_headers)
    assert any("Izveidots lietotāja konts" in record["message"] for record in activity.json())


def test_admin_cannot_demote_or_deactivate_self(client, admin_headers):
    assert client.patch("/api/users/1", json={"role": "LIETOTAJS"}, headers=admin_headers).status_code == 409
    assert client.patch("/api/users/1", json={"isActive": False}, headers=admin_headers).status_code == 409


def test_admin_can_update_user_role(client, admin_headers):
    response = client.patch(
        "/api/users/2",
        json={"role": "ADMIN"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["role"] == "ADMIN"

