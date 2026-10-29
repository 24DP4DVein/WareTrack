import sqlite3

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import create_database_engine
from app.auth.security import validate_auth_configuration
from app.migration_support import (
    HEAD, INVENTORY_BALANCES, current_revision, upgrade_database,
)
from app.models import Category, Company, Item, Location
from app.seed_demo_companies import create_demo_database


def test_jwt_secret_is_required_explicitly(monkeypatch):
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        validate_auth_configuration()
    secret = "explicit-local-secret-key-with-at-least-32-characters"
    monkeypatch.setenv("JWT_SECRET_KEY", secret)
    assert validate_auth_configuration() == secret


def test_final_migration_rejects_unresolved_legacy_ownership(tmp_path):
    database = tmp_path / "legacy.db"
    engine = create_database_engine(f"sqlite:///{database.as_posix()}")
    try:
        upgrade_database(engine, revision=INVENTORY_BALANCES)
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "INSERT INTO categories "
                "(id,name,description,icon,color,created_at,company_id) "
                "VALUES (9,'Legacy','','Package','blue',CURRENT_TIMESTAMP,NULL)"
            )
        with pytest.raises(RuntimeError, match="Unresolved legacy company ownership"):
            upgrade_database(engine)
        with engine.connect() as connection:
            assert current_revision(connection) == INVENTORY_BALANCES
            assert connection.exec_driver_sql(
                "SELECT name FROM categories WHERE id=9"
            ).scalar_one() == "Legacy"
    finally:
        engine.dispose()


def test_final_constraints_reject_null_negative_and_cross_company_data(test_engine):
    with Session(test_engine) as session:
        first = Company(name="Integrity first", slug="integrity-first")
        second = Company(name="Integrity second", slug="integrity-second")
        session.add_all([first, second])
        session.flush()
        first_category = Category(company_id=first.id, name="First")
        first_location = Location(company_id=first.id, code="FIRST", name="First", capacity=10)
        second_location = Location(company_id=second.id, code="SECOND", name="Second", capacity=10)
        session.add_all([first_category, first_location, second_location])
        session.commit()

        session.add(Category(name="Ownerless"))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add(Item(
            company_id=first.id, name="Cross company", sku="CROSS-001",
            category_id=first_category.id, location_id=second_location.id,
            stock=0, min_stock=0, price=1,
        ))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add(Item(
            company_id=first.id, name="Negative", sku="NEGATIVE-001",
            category_id=first_category.id, location_id=first_location.id,
            stock=-1, min_stock=0, price=1,
        ))
        with pytest.raises(IntegrityError):
            session.commit()


def test_demo_generator_is_explicit_isolated_and_idempotent(tmp_path, monkeypatch):
    database = tmp_path / "waretrack-demo.sqlite"
    monkeypatch.setenv("WARETRACK_DEMO_MODE", "1")
    monkeypatch.setenv("WARETRACK_DEMO_PASSWORD", "StrongDemoPassword2026")
    create_demo_database(database)
    create_demo_database(database)

    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == HEAD
        assert connection.execute("SELECT count(*) FROM companies").fetchone()[0] == 3
        assert connection.execute("SELECT count(*) FROM users").fetchone()[0] == 7
        assert connection.execute("SELECT count(*) FROM items").fetchone()[0] == 12
        assert connection.execute("SELECT count(*) FROM transfers").fetchone()[0] == 3
        assert connection.execute("SELECT count(*) FROM inventory_balances").fetchone()[0] == 24
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        mismatches = connection.execute(
            "SELECT i.id FROM items i LEFT JOIN inventory_balances b "
            "ON b.item_id=i.id AND b.company_id=i.company_id "
            "GROUP BY i.id HAVING SUM(b.quantity) != i.stock"
        ).fetchall()
        assert mismatches == []


def test_demo_generator_refuses_unknown_nonempty_database(tmp_path, monkeypatch):
    database = tmp_path / "unknown.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE unrelated (id INTEGER PRIMARY KEY)")
    monkeypatch.setenv("WARETRACK_DEMO_MODE", "1")
    monkeypatch.setenv("WARETRACK_DEMO_PASSWORD", "StrongDemoPassword2026")
    with pytest.raises(RuntimeError, match="not created by this demo generator"):
        create_demo_database(database)
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE name='unrelated'"
        ).fetchone() == ("unrelated",)
