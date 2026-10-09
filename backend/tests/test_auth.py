def test_valid_login(client):
    response = client.post("/api/auth/login", json={"email": "user@test.lv", "password": "User123!"})
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "USER"


def test_invalid_login(client):
    response = client.post("/api/auth/login", json={"email": "user@test.lv", "password": "wrong"})
    assert response.status_code == 401


def test_protected_endpoint(client):
    assert client.get("/api/suppliers").status_code == 401


def test_role_permissions(client, user_headers, admin_headers):
    payload = {"name": "Jauna kategorija", "description": "Apraksts", "icon": "Package", "color": "blue"}
    assert client.post("/api/categories", json=payload, headers=user_headers).status_code == 403
    assert client.post("/api/categories", json=payload, headers=admin_headers).status_code == 201

