import os

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import bootstrap_admin
from app.models import Role, User


def test_bootstrap_is_disabled_by_default(monkeypatch):
    monkeypatch.setenv("WARETRACK_ENV", "development")
    monkeypatch.delenv("WARETRACK_BOOTSTRAP_ADMIN", raising=False)
    monkeypatch.delenv("WARETRACK_ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("WARETRACK_ADMIN_PASSWORD", raising=False)

    result = bootstrap_admin("development")
    assert result["created"] is False
    assert result["reason"] == "explicit bootstrap disabled"


def test_bootstrap_requires_explicit_admin_credentials(monkeypatch):
    monkeypatch.setenv("WARETRACK_ENV", "development")
    monkeypatch.setenv("WARETRACK_BOOTSTRAP_ADMIN", "true")
    monkeypatch.delenv("WARETRACK_ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("WARETRACK_ADMIN_PASSWORD", raising=False)

    with pytest.raises(RuntimeError, match="WARETRACK_ADMIN_EMAIL"):
        bootstrap_admin("development")


def test_bootstrap_creates_admin_when_explicitly_enabled(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setenv("WARETRACK_ENV", "development")
    monkeypatch.setenv("WARETRACK_BOOTSTRAP_ADMIN", "true")
    monkeypatch.setenv("WARETRACK_ADMIN_EMAIL", "dev-admin@waretrack.local")
    monkeypatch.setenv("WARETRACK_ADMIN_PASSWORD", "StrongPassword123!")

    result = bootstrap_admin("development", session_factory=Session)
    assert result["created"] is True
    with Session() as db:
        user = db.scalar(select(User).where(User.email == "dev-admin@waretrack.local"))
        assert user is not None
        assert user.role == Role.ADMIN


def test_production_bootstrap_is_disabled(monkeypatch):
    monkeypatch.setenv("WARETRACK_ENV", "production")
    monkeypatch.setenv("WARETRACK_BOOTSTRAP_ADMIN", "true")
    monkeypatch.setenv("WARETRACK_ADMIN_EMAIL", "prod-admin@waretrack.local")
    monkeypatch.setenv("WARETRACK_ADMIN_PASSWORD", "StrongPassword123!")

    result = bootstrap_admin("production")
    assert result["created"] is False
    assert result["reason"] == "production bootstrap disabled"
