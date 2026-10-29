import pytest


@pytest.mark.parametrize("path", ["/api/items", "/api/categories", "/api/suppliers", "/api/locations"])
def test_legacy_inventory_endpoints_are_disabled(client, path):
    response = client.get(path)
    assert response.status_code == 410
    assert "company-scoped" in response.json()["detail"]

