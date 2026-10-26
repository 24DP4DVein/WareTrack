import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth.security import hash_password
from app.database import Base, get_db
from app.main import app
from app.models import Category, InventoryBalance, Item, Location, Role, Supplier, User

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def override_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_db


@pytest.fixture(autouse=True)
def fresh_database():
    Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
    db = TestingSession()
    admin = User(name="Admin", email="admin@test.lv", password_hash=hash_password("Admin123!"), role="ADMIN")
    user = User(name="User", email="user@test.lv", password_hash=hash_password("User123!"), role=Role.VADITAJS)
    viewer = User(name="Viewer", email="viewer@test.lv", password_hash=hash_password("Viewer123!"), role=Role.LIETOTAJS)
    cat = Category(name="Testa kategorija", description="Testiem", icon="Package", color="blue")
    supplier = Supplier(name="Testa piegādātājs", contact_person="Anna Liepa", email="anna@supplier.lv",
                        phone="+371 20000000", address="Rīga, Latvija", category="Testi", payment_terms="net30")
    loc1 = Location(code="RIG-A01", name="Rīga A1", capacity=1000)
    loc2 = Location(code="RIG-B01", name="Rīga B1", capacity=1000)
    db.add_all([admin, user, viewer, cat, supplier, loc1, loc2]); db.flush()
    item = Item(name="Testa prece", sku="TEST-001", category_id=cat.id, supplier_id=supplier.id,
                min_stock=5, price=10)
    db.add(item); db.flush()
    db.add(InventoryBalance(item_id=item.id, location_id=loc1.id, quantity=20))
    db.commit(); db.close()
    yield


@pytest.fixture
def client():
    return TestClient(app)


def login(client, email="user@test.lv", password="User123!"):
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


@pytest.fixture
def user_headers(client): return login(client)


@pytest.fixture
def admin_headers(client): return login(client, "admin@test.lv", "Admin123!")


@pytest.fixture
def viewer_headers(client): return login(client, "viewer@test.lv", "Viewer123!")

