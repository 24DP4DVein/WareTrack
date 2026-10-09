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

