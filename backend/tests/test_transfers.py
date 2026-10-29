def test_legacy_transfer_endpoints_are_disabled(client, user_headers):
    assert client.get("/api/transfers", headers=user_headers).status_code == 410
    assert client.post("/api/transfers", json={}, headers=user_headers).status_code == 410
    assert client.patch("/api/transfers/1", json={}, headers=user_headers).status_code == 410