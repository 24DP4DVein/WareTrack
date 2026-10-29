"""Create the isolated, explicitly enabled WareTrack multi-company demo database."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3

from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.database import create_database_engine, initialize_database
from app.migration_support import upgrade_database
from app.models import (
    ActivityLog, Category, Company, CompanyMembership, InventoryBalance, Item,
    Location, Supplier, Transfer, User,
)

DEMO_APPLICATION_ID = 0x5754444D  # WTDM
DEMO_SLUGS = ("techstore", "autoparts", "buildmaster")

COMPANIES = (
    {
        "name": "SIA TechStore", "slug": "techstore", "prefix": "TECH",
        "categories": ("Portatīvie datori", "Monitori", "Tastatūras", "Aksesuāri"),
        "items": (
            ("Biznesa portatīvais dators", "LAPTOP", 1299.00, 14, 3),
            ("27 collu monitors", "MONITOR", 329.00, 22, 5),
            ("Mehāniskā tastatūra", "KEYBOARD", 119.00, 30, 7),
            ("USB-C dokstacija", "DOCK", 189.00, 18, 4),
        ),
    },
    {
        "name": "SIA AutoParts", "slug": "autoparts", "prefix": "AUTO",
        "categories": ("Eļļas filtri", "Bremžu diski", "Gaisa filtri", "Siksnas"),
        "items": (
            ("Eļļas filtrs", "OIL-FILTER", 12.50, 80, 20),
            ("Priekšējais bremžu disks", "BRAKE-DISC", 74.00, 36, 8),
            ("Gaisa filtrs", "AIR-FILTER", 18.90, 64, 15),
            ("Piedziņas siksna", "BELT", 31.00, 42, 10),
        ),
    },
    {
        "name": "SIA BuildMaster", "slug": "buildmaster", "prefix": "BUILD",
        "categories": ("Cements", "Krāsas", "Skrūves", "Instrumenti"),
        "items": (
            ("Cements 25 kg", "CEMENT", 8.40, 120, 30),
            ("Interjera krāsa 10 l", "PAINT", 47.00, 28, 6),
            ("Koka skrūves 5x60", "SCREWS", 9.90, 75, 18),
            ("Akumulatora urbjmašīna", "DRILL", 159.00, 16, 4),
        ),
    },
)


def _enabled(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes"}


def _credential_email(slug: str, role: str) -> str:
    key = f"WARETRACK_DEMO_{slug.upper()}_{role.upper()}_EMAIL"
    default = f"{role}.{slug}@demo.invalid"
    return os.environ.get(key, default).strip().lower()


def _password() -> str:
    value = os.environ.get("WARETRACK_DEMO_PASSWORD", "")
    if len(value) < 12 or not any(c.isupper() for c in value) or not any(c.isdigit() for c in value):
        raise RuntimeError(
            "WARETRACK_DEMO_PASSWORD must be at least 12 characters and include "
            "an uppercase letter and a digit"
        )
    return value


def _validate_target(path: Path) -> tuple[Path, bool]:
    path = path.expanduser().resolve()
    if path.suffix.lower() not in {".db", ".sqlite", ".sqlite3"}:
        raise RuntimeError("Demo database must use a dedicated SQLite file")
    forbidden = (Path(__file__).resolve().parents[1] / "waretrack.db").resolve()
    if path == forbidden or any(word in path.name.lower() for word in ("prod", "production", "staging")):
        raise RuntimeError("Refusing a normal, production or staging database path")

    configured = os.environ.get("DATABASE_URL")
    if configured:
        url = make_url(configured)
        if url.get_backend_name() != "sqlite":
            raise RuntimeError("Demo generation refuses while DATABASE_URL targets a non-SQLite database")
        if url.database and url.database != ":memory:":
            configured_path = Path(url.database).expanduser().resolve()
            if configured_path == path:
                raise RuntimeError("Demo path must differ from the normal DATABASE_URL")

    existed = path.exists()
    if existed:
        with sqlite3.connect(path) as connection:
            application_id = connection.execute("PRAGMA application_id").fetchone()[0]
            objects = connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table','view','trigger') "
                "AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        if objects and application_id != DEMO_APPLICATION_ID:
            raise RuntimeError("Refusing an existing database not created by this demo generator")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path, existed


def _get_or_create(session: Session, model, defaults=None, **identity):
    instance = session.scalar(select(model).filter_by(**identity))
    if instance is not None:
        return instance, False
    instance = model(**identity, **(defaults or {}))
    session.add(instance)
    session.flush()
    return instance, True


def _seed(session: Session, password_hash: str) -> None:
    now = datetime.now(timezone.utc)
    admin_email = os.environ.get(
        "WARETRACK_DEMO_ADMIN_EMAIL", "admin@demo.invalid"
    ).strip().lower()
    admin, created = _get_or_create(
        session, User, email=admin_email,
        defaults={"name": "Demo administrators", "password_hash": password_hash,
                  "role": "ADMIN", "is_active": True},
    )
    if not created and (admin.role != "ADMIN" or not admin.is_active):
        raise RuntimeError("Existing demo administrator has an incompatible account state")

    for specification in COMPANIES:
        company, _ = _get_or_create(
            session, Company, slug=specification["slug"],
            defaults={"name": specification["name"], "is_active": True},
        )
        if company.name != specification["name"]:
            raise RuntimeError(f"Demo company slug conflict: {company.slug}")

        users = {}
        for role, local_role, label in (
            ("manager", "VADITAJS", "Vadītājs"),
            ("user", "LIETOTAJS", "Lietotājs"),
        ):
            email = _credential_email(specification["slug"], role)
            user, user_created = _get_or_create(
                session, User, email=email,
                defaults={"name": f"{specification['name']} {label}",
                          "password_hash": password_hash, "role": "USER", "is_active": True},
            )
            if not user_created and (user.role != "USER" or not user.is_active):
                raise RuntimeError(f"Existing demo user has an incompatible state: {email}")
            membership, _ = _get_or_create(
                session, CompanyMembership, company_id=company.id, user_id=user.id,
                defaults={"role": local_role, "is_active": True, "approved_at": now,
                          "approved_by_id": admin.id},
            )
            if membership.role != local_role or not membership.is_active:
                raise RuntimeError(f"Existing demo membership has an incompatible state: {email}")
            users[role] = user

        categories = []
        for name in specification["categories"]:
            category, _ = _get_or_create(
                session, Category, company_id=company.id, name=name,
                defaults={"description": f"{specification['name']} demo kategorija",
                          "icon": "Package", "color": "blue"},
            )
            categories.append(category)

        supplier, _ = _get_or_create(
            session, Supplier, company_id=company.id,
            email=f"supplier.{specification['slug']}@demo.invalid",
            defaults={"name": f"{specification['name']} piegādātājs",
                      "contact_person": "Demo kontakts", "phone": "+371 20000000",
                      "address": "Rīga, Latvija", "category": "Demo",
                      "payment_terms": "net30", "is_active": True},
        )
        source, _ = _get_or_create(
            session, Location, company_id=company.id,
            code=f"{specification['prefix']}-A",
            defaults={"name": "Galvenā noliktava", "capacity": 5000},
        )
        destination, _ = _get_or_create(
            session, Location, company_id=company.id,
            code=f"{specification['prefix']}-B",
            defaults={"name": "Rezerves noliktava", "capacity": 3000},
        )

        seeded_items = []
        for index, (name, sku_suffix, price, stock, minimum) in enumerate(specification["items"]):
            item, item_created = _get_or_create(
                session, Item, company_id=company.id,
                sku=f"{specification['prefix']}-{sku_suffix}",
                defaults={"name": name, "category_id": categories[index].id,
                          "supplier_id": supplier.id, "location_id": source.id,
                          "stock": stock, "min_stock": minimum, "price": price,
                          "description": "WareTrack demonstrācijas prece"},
            )
            if not item_created and item.stock != stock:
                raise RuntimeError(f"Demo item was modified; refusing to overwrite {item.sku}")
            first_quantity = stock - min(3, stock)
            second_quantity = stock - first_quantity
            for location, quantity in ((source, first_quantity), (destination, second_quantity)):
                balance, balance_created = _get_or_create(
                    session, InventoryBalance, company_id=company.id,
                    item_id=item.id, location_id=location.id,
                    defaults={"quantity": quantity, "reserved": 0},
                )
                if not balance_created and (balance.quantity != quantity or balance.reserved != 0):
                    raise RuntimeError(f"Demo balance was modified; refusing to overwrite {item.sku}")
            seeded_items.append(item)

        transfer, _ = _get_or_create(
            session, Transfer, company_id=company.id,
            code=f"DEMO-{specification['prefix']}-001",
            defaults={"item_id": seeded_items[0].id, "source_location_id": source.id,
                      "destination_location_id": destination.id, "quantity": 3,
                      "status": "done", "priority": "normal",
                      "notes": "Pabeigts demonstrācijas pārvietojums",
                      "creator_id": users["manager"].id},
        )
        if transfer.item_id != seeded_items[0].id:
            raise RuntimeError(f"Demo transfer code conflict: {transfer.code}")

        if session.scalar(select(ActivityLog.id).where(
            ActivityLog.company_id == company.id, ActivityLog.action == "demo_seed"
        )) is None:
            session.add_all([
                ActivityLog(company_id=company.id, user_id=admin.id, action="demo_seed",
                            entity_type="company", entity_id=str(company.id),
                            message=f"Izveidoti {specification['name']} demonstrācijas dati"),
                ActivityLog(company_id=company.id, user_id=users["manager"].id,
                            action="transfer_done", entity_type="transfer",
                            entity_id=str(transfer.id), message="Pabeigts demo pārvietojums"),
            ])


def create_demo_database(path: str | Path) -> Path:
    if not _enabled(os.environ.get("WARETRACK_DEMO_MODE")):
        raise RuntimeError("Set WARETRACK_DEMO_MODE=1 to enable demo generation explicitly")
    password_hash = hash_password(_password())
    path, existed = _validate_target(Path(path))
    engine = create_database_engine(f"sqlite:///{path.as_posix()}")
    try:
        upgrade_database(engine)
        with engine.connect() as connection:
            unknown = connection.exec_driver_sql(
                "SELECT slug FROM companies WHERE slug NOT IN (?, ?, ?)", DEMO_SLUGS
            ).scalars().all()
            if unknown:
                raise RuntimeError("Demo database contains unknown companies: " + ", ".join(unknown))
        with Session(engine) as session, session.begin():
            _seed(session, password_hash)
        with engine.begin() as connection:
            connection.exec_driver_sql(f"PRAGMA application_id = {DEMO_APPLICATION_ID}")
        initialize_database(engine)
    except BaseException:
        engine.dispose()
        if not existed and path.exists():
            path.unlink()
        raise
    finally:
        engine.dispose()
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    args = parser.parse_args(argv)
    created = create_demo_database(args.database)
    print(f"Demo database ready: {created}")
    print("Credentials were read from WARETRACK_DEMO_* environment variables; passwords are not displayed.")


if __name__ == "__main__":
    main()
