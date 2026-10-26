import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.migrations import migrate_user_roles
from app.models import Role, User


def test_role_migration_preserves_accounts_and_maps_legacy_values():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT, password_hash TEXT, role TEXT)"
        )
        connection.exec_driver_sql(
            "INSERT INTO users VALUES (1, 'manager@test.lv', 'hash-1', 'USER'), "
            "(2, 'admin@test.lv', 'hash-2', 'ADMIN')"
        )

    migrate_user_roles(engine)

    with engine.connect() as connection:
        users = connection.execute(text("SELECT id, email, password_hash, role FROM users ORDER BY id")).all()
    assert users == [
        (1, "manager@test.lv", "hash-1", "VADITAJS"),
        (2, "admin@test.lv", "hash-2", "ADMIN"),
    ]
    engine.dispose()


def test_development_seed_creates_all_three_roles_and_catalog(monkeypatch, tmp_path):
    from app import seed as seed_module

    engine = create_engine(f"sqlite:///{tmp_path / 'seed.db'}")
    monkeypatch.setattr(seed_module, "engine", engine)
    monkeypatch.setattr(seed_module, "SessionLocal", sessionmaker(bind=engine, autoflush=False, autocommit=False))
    monkeypatch.setenv("WARETRACK_ENV", "development")

    seed_module.seed()

    with sessionmaker(bind=engine)() as db:
        roles = set(db.scalars(select(User.role)))
        users = list(db.scalars(select(User)))
        assert roles == {Role.LIETOTAJS, Role.VADITAJS, Role.ADMIN}
        assert len(users) == 3
        assert users[0].id is not None
    engine.dispose()


def test_seed_refuses_to_create_demo_credentials_outside_dev_and_test(monkeypatch):
    from app.seed import seed

    monkeypatch.setenv("WARETRACK_ENV", "production")
    with pytest.raises(RuntimeError, match="restricted to development and test"):
        seed()