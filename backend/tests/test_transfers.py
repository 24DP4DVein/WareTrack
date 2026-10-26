def transfer_payload(quantity=3, destination=2):
    return {"itemId": 1, "sourceLocationId": 1, "destinationLocationId": destination,
            "quantity": quantity, "priority": "normal", "notes": "Tests"}


def test_valid_transfer(client, user_headers):
    response = client.post("/api/transfers", json=transfer_payload(), headers=user_headers)
    assert response.status_code == 201
    assert response.json()["status"] == "pending"


def test_invalid_quantity(client, user_headers):
    assert client.post("/api/transfers", json=transfer_payload(0), headers=user_headers).status_code == 422
    assert client.post("/api/transfers", json=transfer_payload(99), headers=user_headers).status_code == 422


def test_identical_locations(client, user_headers):
    response = client.post("/api/transfers", json=transfer_payload(destination=1), headers=user_headers)
    assert response.status_code == 422

def test_transfer_validation_rejects_negative_quantity(client, user_headers):
    response = client.post(
        "/api/transfers",
        json=transfer_payload(-1),
        headers=user_headers,
    )
    assert response.status_code == 422


def test_transfer_validation_rejects_invalid_priority(client, user_headers):
    data = transfer_payload()
    data["priority"] = "super-urgent"
    response = client.post("/api/transfers", json=data, headers=user_headers)
    assert response.status_code == 422


def test_partial_transfer_moves_only_requested_units(client, user_headers):
    created = client.post("/api/transfers", json=transfer_payload(3), headers=user_headers)
    assert created.status_code == 201
    transfer_id = created.json()["id"]
    assert client.patch(
        f"/api/transfers/{transfer_id}",
        json={"status": "in-transit"},
        headers=user_headers,
    ).status_code == 200
    completed = client.patch(
        f"/api/transfers/{transfer_id}",
        json={"status": "done"},
        headers=user_headers,
    )
    assert completed.status_code == 200
    item = client.get("/api/items/1", headers=user_headers).json()
    assert item["stock"] == 20
    balances = {row["locationId"]: row["quantity"] for row in item["locations"]}
    assert balances == {1: 17, 2: 3}

    duplicate = client.patch(
        f"/api/transfers/{transfer_id}",
        json={"status": "done"},
        headers=user_headers,
    )
    assert duplicate.status_code == 422


def test_cancelled_transfer_does_not_change_stock(client, user_headers):
    created = client.post("/api/transfers", json=transfer_payload(3), headers=user_headers).json()
    cancelled = client.patch(
        f"/api/transfers/{created['id']}",
        json={"status": "cancelled"},
        headers=user_headers,
    )
    assert cancelled.status_code == 200
    item = client.get("/api/items/1", headers=user_headers).json()
    assert item["stock"] == 20
