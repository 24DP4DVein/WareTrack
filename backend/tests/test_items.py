def payload(sku="NEW-001", stock=10):
    return {"name": "Jauna testa prece", "sku": sku, "categoryId": 1, "supplierId": 1,
            "locationId": 1, "stock": stock, "minStock": 2, "price": 5.5, "description": "Tests"}


def test_list_items(client):
    response = client.get("/api/items")
    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_create_item(client, user_headers):
    response = client.post("/api/items", json=payload(), headers=user_headers)
    assert response.status_code == 201
    assert response.json()["sku"] == "NEW-001"


def test_item_validation(client, user_headers):
    response = client.post("/api/items", json=payload(stock=-1), headers=user_headers)
    assert response.status_code == 422


def test_duplicate_sku(client, user_headers):
    response = client.post("/api/items", json=payload("TEST-001"), headers=user_headers)
    assert response.status_code == 409


def test_update_item(client, user_headers):
    data = payload("TEST-001", 33); data["name"] = "Labota testa prece"
    response = client.put("/api/items/1", json=data, headers=user_headers)
    assert response.status_code == 200
    assert response.json()["stock"] == 33


def test_delete_item(client, user_headers):
    created = client.post("/api/items", json=payload(), headers=user_headers).json()
    response = client.delete(f"/api/items/{created['id']}", headers=user_headers)
    assert response.status_code == 204

