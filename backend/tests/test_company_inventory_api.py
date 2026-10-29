from datetime import datetime, timezone

from alembic import command
from sqlalchemy import select

from app.database import create_database_engine
from app.migration_support import (
    COMPANY_OWNERSHIP, INVENTORY_BALANCES, current_revision, migration_config,
    upgrade_database,
)
from app.models import ActivityLog, Category, Company, CompanyJoinRequest, CompanyMembership, Item, Location, Supplier, User


def category_payload(name="Shared category"):
    return {"name": name, "description": "Tests", "icon": "Package", "color": "blue"}


def supplier_payload(name="Shared supplier", email="shared@supplier.lv"):
    return {"name": name, "contactPerson": "Test Person", "email": email,
            "phone": "+371 20000000", "address": "Riga, Test street 1",
            "category": "Tests", "paymentTerms": "net30"}


def location_payload(code="SHARED-01"):
    return {"code": code, "name": "Shared location", "capacity": 1000}


def item_payload(resources, sku="SHARED-SKU"):
    return {"name": "Shared item", "sku": sku, "categoryId": resources["category"],
            "supplierId": resources["supplier"], "locationId": resources["location"],
            "stock": 10, "minStock": 2, "price": 5.5, "description": "Tests"}


def build_company_data(fresh_database):
    with fresh_database() as db:
        user = db.scalar(select(User).where(User.email == "user@test.lv"))
        first = Company(name="First company", slug="first-company")
        second = Company(name="Second company", slug="second-company")
        pending = Company(name="Pending company", slug="pending-company")
        inactive = Company(name="Inactive membership", slug="inactive-membership")
        db.add_all([first, second, pending, inactive]); db.flush()
        db.add_all([
            CompanyMembership(company_id=first.id, user_id=user.id, role="LIETOTAJS",
                              approved_at=datetime.now(timezone.utc)),
            CompanyMembership(company_id=second.id, user_id=user.id, role="VADITAJS",
                              approved_at=datetime.now(timezone.utc)),
            CompanyMembership(company_id=inactive.id, user_id=user.id, role="VADITAJS",
                              approved_at=datetime.now(timezone.utc), is_active=False),
            CompanyJoinRequest(company_id=pending.id, user_id=user.id, status="PENDING"),
        ])
        resources = {}
        for company, suffix in ((first, "A"), (second, "B")):
            category = Category(company_id=company.id, name=f"Category {suffix}")
            supplier = Supplier(company_id=company.id, name=f"Supplier {suffix}",
                                contact_person="Contact", email=f"{suffix.lower()}@supplier.test",
                                phone="1234567", address="Test address", category="Tests",
                                payment_terms="net30")
            source = Location(company_id=company.id, code=f"{suffix}-01", name=f"Source {suffix}", capacity=1000)
            destination = Location(company_id=company.id, code=f"{suffix}-02", name=f"Destination {suffix}", capacity=1000)
            db.add_all([category, supplier, source, destination]); db.flush()
            item = Item(company_id=company.id, name=f"Visible {suffix}", sku=f"SKU-{suffix}",
                        category_id=category.id, supplier_id=supplier.id, location_id=source.id,
                        stock=10, min_stock=2, price=5)
            db.add(item); db.flush()
            resources[company.id] = {"category": category.id, "supplier": supplier.id,
                                     "location": source.id, "item": item.id}
        db.commit()
        return {"first": first.id, "second": second.id, "pending": pending.id,
                "inactive": inactive.id, "resources": resources}


def test_list_detail_search_and_pagination_are_company_isolated(client, fresh_database, user_headers):
    data = build_company_data(fresh_database)
    first, second = data["first"], data["second"]
    response = client.get(f"/api/companies/{first}/items?search=Visible&page=1&page_size=1", headers=user_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["id"] == data["resources"][first]["item"]
    assert client.get(f"/api/companies/{first}/items/{data['resources'][second]['item']}", headers=user_headers).status_code == 404
    assert client.get(f"/api/companies/{first}/categories/{data['resources'][second]['category']}", headers=user_headers).status_code == 404
    assert client.get(f"/api/companies/{first}/categories", headers=user_headers).json()[0]["itemCount"] == 1
    locations = client.get(f"/api/companies/{first}/locations", headers=user_headers).json()
    assert sorted(location["usedCapacity"] for location in locations) == [0, 10]


def test_permissions_pending_inactive_and_admin(client, fresh_database, user_headers, admin_headers):
    data = build_company_data(fresh_database)
    assert client.post(f"/api/companies/{data['first']}/categories", json=category_payload("Denied"), headers=user_headers).status_code == 403
    assert client.post(f"/api/companies/{data['second']}/categories", json=category_payload("Managed"), headers=user_headers).status_code == 201
    assert client.get(f"/api/companies/{data['pending']}/items", headers=user_headers).status_code == 403
    assert client.get(f"/api/companies/{data['inactive']}/items", headers=user_headers).status_code == 403
    assert client.get(f"/api/companies/{data['first']}/items", headers=admin_headers).status_code == 200


def test_item_relations_ownership_and_activity(client, fresh_database, user_headers):
    data = build_company_data(fresh_database)
    first, second = data["first"], data["second"]
    assert client.post(f"/api/companies/{first}/items", json=item_payload(data["resources"][second], "CROSS"), headers=user_headers).status_code == 422
    response = client.post(f"/api/companies/{first}/items", json=item_payload(data["resources"][first], "SERVER-OWNER"), headers=user_headers)
    assert response.status_code == 201
    with fresh_database() as db:
        item = db.get(Item, response.json()["id"])
        activity = db.scalar(select(ActivityLog).where(ActivityLog.entity_id == str(item.id)).order_by(ActivityLog.id.desc()))
        assert item.company_id == first
        assert activity.company_id == first


def test_item_and_master_data_update_delete(client, fresh_database, user_headers):
    data = build_company_data(fresh_database)
    first, second = data["first"], data["second"]
    resources = data["resources"][first]
    updated_item = item_payload(resources, "SKU-A")
    updated_item.update(name="Updated item", stock=25)
    response = client.put(
        f"/api/companies/{first}/items/{resources['item']}",
        json=updated_item, headers=user_headers,
    )
    assert response.status_code == 200 and response.json()["stock"] == 25

    created = client.post(
        f"/api/companies/{second}/categories",
        json=category_payload("Temporary category"), headers=user_headers,
    )
    assert created.status_code == 201
    category_id = created.json()["id"]
    updated = client.put(
        f"/api/companies/{second}/categories/{category_id}",
        json=category_payload("Renamed category"), headers=user_headers,
    )
    assert updated.status_code == 200 and updated.json()["name"] == "Renamed category"
    assert client.delete(
        f"/api/companies/{second}/categories/{category_id}", headers=user_headers
    ).status_code == 204


def test_uniqueness_is_per_company(client, fresh_database, admin_headers, user_headers):
    data = build_company_data(fresh_database)
    first, second = data["first"], data["second"]
    for path, payload in (("categories", category_payload()), ("suppliers", supplier_payload()), ("locations", location_payload())):
        assert client.post(f"/api/companies/{first}/{path}", json=payload, headers=admin_headers).status_code == 201
        assert client.post(f"/api/companies/{first}/{path}", json=payload, headers=admin_headers).status_code == 409
        assert client.post(f"/api/companies/{second}/{path}", json=payload, headers=admin_headers).status_code == 201
    for company_id in (first, second):
        payload = item_payload(data["resources"][company_id])
        assert client.post(f"/api/companies/{company_id}/items", json=payload, headers=user_headers).status_code == 201
        assert client.post(f"/api/companies/{company_id}/items", json=payload, headers=user_headers).status_code == 409


def test_legacy_routes_do_not_expose_company_data(client, fresh_database):
    build_company_data(fresh_database)
    for path in ("items", "categories", "suppliers", "locations", "transfers", "dashboard", "reports", "activity"):
        assert client.get(f"/api/{path}").status_code == 410


def test_uniqueness_migration_preserves_legacy_null_owned_rows(tmp_path):
    engine = create_database_engine(f"sqlite:///{(tmp_path / 'scoped.db').as_posix()}")
    try:
        with engine.connect() as connection:
            command.upgrade(migration_config(connection), COMPANY_OWNERSHIP)
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "INSERT INTO categories (id,name,description,icon,color,created_at,company_id) "
                "VALUES (501,'Legacy','','Package','blue',CURRENT_TIMESTAMP,NULL)"
            )
            before = connection.exec_driver_sql("SELECT * FROM categories WHERE id=501").one()
        upgrade_database(engine, revision=INVENTORY_BALANCES)
        with engine.connect() as connection:
            assert current_revision(connection) == INVENTORY_BALANCES
            assert connection.exec_driver_sql("SELECT * FROM categories WHERE id=501").one() == before
    finally:
        engine.dispose()
