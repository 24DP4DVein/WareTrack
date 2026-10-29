import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Do not inherit a developer, staging or production connection string.
# Fail closed if another test/plugin imported the application too early.
if "app.database" in sys.modules or "app.main" in sys.modules:
    raise pytest.UsageError("Configure the isolated database before importing app modules")
os.environ["DATABASE_URL"] = "sqlite://"

from app.auth.security import hash_password
from app.database import create_database_engine, engine as application_engine, get_db, initialize_database
from app.main import app
from app.models import Category, Item, Location, Supplier, User


@event.listens_for(application_engine, "do_connect")
def forbid_application_database(*_):
    raise AssertionError("Tests must not connect through the application engine")


@pytest.fixture
def test_engine():
    engine = create_database_engine("sqlite://", poolclass=StaticPool)
    try:
        initialize_database(engine)
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def fresh_database(test_engine):
    TestingSession = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    with TestingSession() as db:
        populate_database(db)
    return TestingSession


def populate_database(db):
    admin = User(name="Admin", email="admin@test.lv", password_hash=hash_password("Admin123!"), role="ADMIN")
    user = User(name="User", email="user@test.lv", password_hash=hash_password("User123!"), role="USER")
    cat = Category(name="Testa kategorija", description="Testiem", icon="Package", color="blue")
    supplier = Supplier(name="Testa pieg─üd─üt─üjs", contact_person="Anna Liepa", email="anna@supplier.lv",
                        phone="+371 20000000", address="R─½ga, Latvija", category="Testi", payment_terms="net30")
    loc1 = Location(code="RIG-A01", name="R─½ga A1", capacity=1000)
    loc2 = Location(code="RIG-B01", name="R─½ga B1", capacity=1000)
    db.add_all([admin, user, cat, supplier, loc1, loc2]); db.flush()
    db.add(Item(name="Testa prece", sku="TEST-001", category_id=cat.id, supplier_id=supplier.id,
                location_id=loc1.id, stock=20, min_stock=5, price=10))
    db.commit()


@pytest.fixture
def client(fresh_database, test_engine):
    def override_db():
        with fresh_database() as db:
            yield db

    previous_overrides = app.dependency_overrides.copy()
    previous_engine = app.state.database_engine
    app.state.database_engine = test_engine
    app.dependency_overrides[get_db] = override_db
    try:
        # Enter lifespan as in a real server, but with the per-test engine.
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        app.state.database_engine = previous_engine


def login(client, email="user@test.lv", password="User123!"):
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


@pytest.fixture
def user_headers(client): return login(client)


@pytest.fixture
def admin_headers(client): return login(client, "admin@test.lv", "Admin123!")

