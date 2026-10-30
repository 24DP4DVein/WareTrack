"""Explicitly seed the configured WareTrack database for demo/testing only."""

from __future__ import annotations

import os

from sqlalchemy.orm import Session

from app.database import engine, initialize_database
from app.migration_support import upgrade_database
from app.seed_demo_companies import _password, _seed
from app.auth.security import hash_password


def main() -> None:
    demo_mode = os.environ.get("WARETRACK_DEMO_MODE", "").strip().lower()

    if demo_mode not in {"1", "true", "yes"}:
        raise RuntimeError(
            "Set WARETRACK_DEMO_MODE=1 to enable demo seeding explicitly"
        )

    if engine.dialect.name != "sqlite":
        raise RuntimeError("Demo seeding is supported only for SQLite databases")

    # Apply database migrations before creating demo data.
    upgrade_database(engine)

    password_hash = hash_password(_password())

    with Session(engine) as session, session.begin():
        _seed(session, password_hash)

    initialize_database(engine)

    admin_email = os.environ.get(
        "WARETRACK_DEMO_ADMIN_EMAIL",
        "admin@demo.waretrack.lv",
    ).strip().lower()

    print("WareTrack demo data is ready.")
    print(f"Admin email: {admin_email}")
    print("Demo password is not printed.")


if __name__ == "__main__":
    main()
