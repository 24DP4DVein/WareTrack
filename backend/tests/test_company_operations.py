from datetime import datetime, timezone

from sqlalchemy import select

from app.models import (
    ActivityLog, Company, CompanyJoinRequest, CompanyMembership,
    InventoryBalance, Item, User,
)
from test_company_inventory_api import build_company_data


def prepare_operations(fresh_database):
    data = build_company_data(fresh_database)
    with fresh_database() as db:
        for company_id, resources in data["resources"].items():
            item = db.get(Item, resources["item"])
            db.add(InventoryBalance(
                company_id=company_id, item_id=item.id,
                location_id=resources["location"], quantity=item.stock, reserved=0,
            ))
        db.commit()
    return data


def transfer_payload(resources, destination, quantity=4):
    return {
        "itemId": resources["item"],
        "sourceLocationId": resources["location"],
        "destinationLocationId": destination,
        "quantity": quantity,
        "priority": "normal",
        "notes": "Company transfer",
    }


def balances(fresh_database, company_id, item_id):
    with fresh_database() as db:
        rows = db.scalars(select(InventoryBalance).where(
            InventoryBalance.company_id == company_id,
            InventoryBalance.item_id == item_id,
        ).order_by(InventoryBalance.location_id)).all()
        return [(row.location_id, row.quantity, row.reserved) for row in rows]


def test_partial_transfer_reservation_completion_and_duplicate_rejection(
    client, fresh_database, user_headers,
):
    data = prepare_operations(fresh_database)
    company_id = data["first"]
    resources = data["resources"][company_id]
    with fresh_database() as db:
        item = db.get(Item, resources["item"])
        destination = next(
            location.id for location in item.company.locations
            if location.id != resources["location"]
        )

    created = client.post(
        f"/api/companies/{company_id}/transfers",
        json=transfer_payload(resources, destination), headers=user_headers,
    )
    assert created.status_code == 201
    transfer_id = created.json()["id"]
    assert balances(fresh_database, company_id, resources["item"]) == [
        (resources["location"], 10, 4)
    ]
    over_reserved = client.post(
        f"/api/companies/{company_id}/transfers",
        json=transfer_payload(resources, destination, 7), headers=user_headers,
    )
    assert over_reserved.status_code == 422

    assert client.patch(
        f"/api/companies/{company_id}/transfers/{transfer_id}",
        json={"status": "in-transit"}, headers=user_headers,
    ).status_code == 200
    completed = client.patch(
        f"/api/companies/{company_id}/transfers/{transfer_id}",
        json={"status": "done"}, headers=user_headers,
    )
    assert completed.status_code == 200
    assert balances(fresh_database, company_id, resources["item"]) == [
        (resources["location"], 6, 0), (destination, 4, 0)
    ]
    assert client.patch(
        f"/api/companies/{company_id}/transfers/{transfer_id}",
        json={"status": "done"}, headers=user_headers,
    ).status_code == 422
    assert balances(fresh_database, company_id, resources["item"]) == [
        (resources["location"], 6, 0), (destination, 4, 0)
    ]
    with fresh_database() as db:
        assert db.get(Item, resources["item"]).stock == 10


def test_cancellation_delete_and_atomic_over_reservation(client, fresh_database, user_headers):
    data = prepare_operations(fresh_database)
    company_id = data["first"]
    resources = data["resources"][company_id]
    with fresh_database() as db:
        item = db.get(Item, resources["item"])
        destination = next(location.id for location in item.company.locations if location.id != item.location_id)
    first = client.post(
        f"/api/companies/{company_id}/transfers",
        json=transfer_payload(resources, destination, 6), headers=user_headers,
    )
    assert first.status_code == 201
    assert client.post(
        f"/api/companies/{company_id}/transfers",
        json=transfer_payload(resources, destination, 5), headers=user_headers,
    ).status_code == 422
    assert client.patch(
        f"/api/companies/{company_id}/transfers/{first.json()['id']}",
        json={"status": "cancelled"}, headers=user_headers,
    ).status_code == 200
    assert balances(fresh_database, company_id, resources["item"])[0][2] == 0
    pending = client.post(
        f"/api/companies/{company_id}/transfers",
        json=transfer_payload(resources, destination, 5), headers=user_headers,
    )
    assert client.delete(
        f"/api/companies/{company_id}/transfers/{pending.json()['id']}",
        headers=user_headers,
    ).status_code == 204
    assert balances(fresh_database, company_id, resources["item"])[0][2] == 0


def test_cross_company_ids_and_transfer_ids_are_hidden(client, fresh_database, user_headers):
    data = prepare_operations(fresh_database)
    first, second = data["first"], data["second"]
    first_resources = data["resources"][first]
    second_resources = data["resources"][second]
    payload = transfer_payload(first_resources, second_resources["location"])
    assert client.post(
        f"/api/companies/{first}/transfers", json=payload, headers=user_headers
    ).status_code == 404
    with fresh_database() as db:
        second_item = db.get(Item, second_resources["item"])
        second_destination = next(
            location.id for location in second_item.company.locations
            if location.id != second_item.location_id
        )
    created = client.post(
        f"/api/companies/{second}/transfers",
        json=transfer_payload(second_resources, second_destination), headers=user_headers,
    )
    assert created.status_code == 201
    assert client.get(
        f"/api/companies/{first}/transfers/{created.json()['id']}", headers=user_headers
    ).status_code == 404


def test_dashboard_reports_activity_and_access_are_company_scoped(
    client, fresh_database, user_headers, admin_headers,
):
    data = prepare_operations(fresh_database)
    first, second = data["first"], data["second"]
    first_resources = data["resources"][first]
    with fresh_database() as db:
        item = db.get(Item, first_resources["item"])
        destination = next(location.id for location in item.company.locations if location.id != item.location_id)
        db.add(ActivityLog(
            company_id=second, action="secret", entity_type="item",
            message="Foreign activity", created_at=datetime.now(timezone.utc),
        ))
        db.commit()
    created = client.post(
        f"/api/companies/{first}/transfers",
        json=transfer_payload(first_resources, destination), headers=user_headers,
    )
    transfer_id = created.json()["id"]
    client.patch(f"/api/companies/{first}/transfers/{transfer_id}", json={"status": "in-transit"}, headers=user_headers)
    client.patch(f"/api/companies/{first}/transfers/{transfer_id}", json={"status": "done"}, headers=user_headers)

    dashboard = client.get(f"/api/companies/{first}/dashboard", headers=user_headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["totalItems"] == 1
    assert dashboard.json()["totalUnits"] == 10
    reports = client.get(f"/api/companies/{first}/reports", headers=user_headers)
    assert reports.status_code == 200
    assert reports.json()["completedTransfers"] == 1
    assert reports.json()["topItems"][0]["movement"] == 4
    activity = client.get(f"/api/companies/{first}/activity", headers=user_headers)
    assert activity.status_code == 200
    assert all(row["message"] != "Foreign activity" for row in activity.json())
    assert client.get(f"/api/companies/{data['pending']}/dashboard", headers=user_headers).status_code == 403
    assert client.get(f"/api/companies/{data['inactive']}/reports", headers=user_headers).status_code == 403
    assert client.get(f"/api/companies/{second}/dashboard", headers=admin_headers).status_code == 200


def test_legacy_item_without_balance_requires_explicit_conversion(
    client, fresh_database, user_headers,
):
    data = build_company_data(fresh_database)
    company_id = data["first"]
    resources = data["resources"][company_id]
    with fresh_database() as db:
        item = db.get(Item, resources["item"])
        destination = next(location.id for location in item.company.locations if location.id != item.location_id)
    response = client.post(
        f"/api/companies/{company_id}/transfers",
        json=transfer_payload(resources, destination), headers=user_headers,
    )
    assert response.status_code == 409
    assert "not initialized" in response.json()["detail"]
