from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

from alembic import command
import pytest
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.database import create_database_engine
from app.migration_support import (
    COMPANY_MODELS,
    HEAD,
    current_revision,
    migration_config,
    upgrade_database,
    validate_revision,
)
from app.models import ActivityLog, Company, Item, Location, Transfer, User
from app.ownership_backfill import (
    OWNED_TABLES,
    OwnershipAssignment,
    OwnershipPlan,
    load_ownership_plan,
    run_ownership_backfill,
)

BACKEND = Path(__file__).resolve().parents[1]


def approved_plan(assignments):
    return OwnershipPlan(
        approved_by="Project owner",
        approved_at=datetime.now(timezone.utc),
        reason="Approved legacy ownership registry",
        assignments=tuple(assignments),
    )


def assignments_for_all_rows(engine, company_id):
    assignments = []
    with engine.connect() as connection:
        for table in OWNED_TABLES:
            assignments.extend(
                OwnershipAssignment(table, row_id, company_id)
                for row_id in connection.execute(text(f'SELECT id FROM "{table}"')).scalars()
            )
    return assignments


def test_upgrade_from_company_models_adds_only_nullable_ownership(tmp_path):
    engine = create_database_engine(f"sqlite:///{(tmp_path / 'ownership.db').as_posix()}")
    try:
        with engine.connect() as connection:
            command.upgrade(migration_config(connection), COMPANY_MODELS)
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "INSERT INTO users VALUES "
                "(11, 'Legacy', 'legacy@test.lv', 'hash', 'USER', 1, CURRENT_TIMESTAMP)"
            )
            connection.exec_driver_sql(
                "INSERT INTO categories VALUES "
                "(21, 'Legacy category', '', 'Package', 'blue', CURRENT_TIMESTAMP)"
            )
            connection.exec_driver_sql(
                "INSERT INTO suppliers VALUES (31, 'Legacy supplier', 'Contact', "
                "'legacy-supplier@test.lv', '1234567', 'Address', 'Legacy', 'net30', 1, "
                "CURRENT_TIMESTAMP)"
            )
            connection.exec_driver_sql(
                "INSERT INTO locations VALUES "
                "(41, 'SOURCE', 'Source', 1000, CURRENT_TIMESTAMP), "
                "(42, 'DEST', 'Destination', 1000, CURRENT_TIMESTAMP)"
            )
            connection.exec_driver_sql(
                "INSERT INTO items VALUES (51, 'Legacy item', 'LEGACY', 21, 31, 41, 7, 1, "
                "12.5, 'kept', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
            connection.exec_driver_sql(
                "INSERT INTO transfers VALUES (61, 'LEGACY-TRANSFER', 51, 41, 42, 2, "
                "'pending', 'normal', 'kept', 11, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
            connection.exec_driver_sql(
                "INSERT INTO activity_logs VALUES "
                "(71, 11, 'create', 'item', '51', 'kept', CURRENT_TIMESTAMP)"
            )
        with engine.connect() as connection:
            before = {
                table: connection.exec_driver_sql(f'SELECT * FROM "{table}" ORDER BY id').all()
                for table in OWNED_TABLES
            }

        upgrade_database(engine)

        inspector = inspect(engine)
        with engine.connect() as connection:
            assert current_revision(connection) == HEAD
            validate_revision(connection, HEAD)
            for table in OWNED_TABLES:
                after = connection.exec_driver_sql(
                    f'SELECT * FROM "{table}" ORDER BY id'
                ).all()
                assert [tuple(row)[:-1] for row in after] == [tuple(row) for row in before[table]]
                assert all(tuple(row)[-1] is None for row in after)
                company_column = next(
                    column for column in inspector.get_columns(table) if column["name"] == "company_id"
                )
                assert company_column["nullable"] is True
                assert any(
                    fk["referred_table"] == "companies"
                    and fk["constrained_columns"] == ["company_id"]
                    for fk in inspector.get_foreign_keys(table)
                )
                assert any(
                    index["name"] == f"ix_{table}_company_id"
                    for index in inspector.get_indexes(table)
                )
    finally:
        engine.dispose()


def test_backfill_dry_run_apply_and_idempotency_preserve_data(fresh_database, test_engine):
    with fresh_database() as session:
        company = Company(name="Legacy owner", slug="legacy-owner")
        session.add(company)
        session.flush()
        item = session.query(Item).one()
        locations = session.query(Location).order_by(Location.id).all()
        user = session.query(User).filter_by(email="user@test.lv").one()
        session.add_all([
            Transfer(
                code="BACKFILL-TRANSFER",
                item_id=item.id,
                source_location_id=locations[0].id,
                destination_location_id=locations[1].id,
                quantity=1,
                creator_id=user.id,
            ),
            ActivityLog(
                user_id=user.id,
                action="test",
                entity_type="item",
                entity_id=str(item.id),
                message="Preserve this",
            ),
        ])
        session.commit()
        company_id = company.id

    with test_engine.connect() as connection:
        before = connection.execute(
            text("SELECT id, name, sku, stock, price FROM items ORDER BY id")
        ).all()
    plan = approved_plan(assignments_for_all_rows(test_engine, company_id))

    dry_run = run_ownership_backfill(test_engine, plan)
    assert dry_run.dry_run is True and dry_run.rows_updated == 0
    with test_engine.connect() as connection:
        assert sum(
            connection.execute(
                text(f'SELECT count(*) FROM "{table}" WHERE company_id IS NOT NULL')
            ).scalar_one()
            for table in OWNED_TABLES
        ) == 0

    applied = run_ownership_backfill(test_engine, plan, apply=True)
    assert applied.dry_run is False
    assert applied.rows_updated == applied.assignments_checked
    with test_engine.connect() as connection:
        assert connection.execute(
            text("SELECT id, name, sku, stock, price FROM items ORDER BY id")
        ).all() == before
        for table in OWNED_TABLES:
            assert connection.execute(
                text(f'SELECT count(*) FROM "{table}" WHERE company_id != :company_id'),
                {"company_id": company_id},
            ).scalar_one() == 0

    repeated = run_ownership_backfill(test_engine, plan, apply=True)
    assert repeated.rows_updated == 0


def test_incomplete_or_cross_company_plan_writes_nothing(fresh_database, test_engine):
    with fresh_database() as session:
        first = Company(name="First owner", slug="first-owner")
        second = Company(name="Second owner", slug="second-owner")
        session.add_all([first, second])
        session.commit()
        first_id, second_id = first.id, second.id

    complete = assignments_for_all_rows(test_engine, first_id)
    incomplete = approved_plan(complete[:-1])
    with pytest.raises(ValueError, match="Unresolved ownership"):
        run_ownership_backfill(test_engine, incomplete, apply=True)

    conflicting = list(complete)
    item_index = next(
        index for index, assignment in enumerate(conflicting) if assignment.table == "items"
    )
    item = conflicting[item_index]
    conflicting[item_index] = OwnershipAssignment(item.table, item.row_id, second_id)
    with pytest.raises(ValueError, match="Cross-company"):
        run_ownership_backfill(test_engine, approved_plan(conflicting), apply=True)

    with test_engine.connect() as connection:
        for table in OWNED_TABLES:
            assert connection.execute(
                text(f'SELECT count(*) FROM "{table}" WHERE company_id IS NOT NULL')
            ).scalar_one() == 0


def test_backfill_rejects_unknown_company_row_and_duplicate(fresh_database, test_engine):
    with fresh_database() as session:
        company = Company(name="Owner", slug="owner")
        session.add(company)
        session.commit()
        company_id = company.id
    complete = assignments_for_all_rows(test_engine, company_id)

    unknown_company = list(complete)
    first = unknown_company[0]
    unknown_company[0] = OwnershipAssignment(first.table, first.row_id, 999999)
    with pytest.raises(ValueError, match="Unknown company"):
        run_ownership_backfill(test_engine, approved_plan(unknown_company), apply=True)

    with pytest.raises(ValueError, match="Unknown row"):
        run_ownership_backfill(
            test_engine,
            approved_plan(complete + [OwnershipAssignment("items", 999999, company_id)]),
            apply=True,
        )
    with pytest.raises(ValueError, match="Duplicate ownership"):
        run_ownership_backfill(test_engine, approved_plan(complete + [complete[0]]), apply=True)


def test_plan_file_requires_approval_metadata_and_timezone(tmp_path):
    plan_path = tmp_path / "ownership.json"
    document = {
        "approved_by": "Project owner",
        "approved_at": "2026-10-29T12:00:00+02:00",
        "reason": "Approved registry",
        "assignments": [{"table": "items", "id": 1, "company_id": 2}],
    }
    plan_path.write_text(json.dumps(document), encoding="utf-8")
    plan = load_ownership_plan(plan_path)
    assert plan.assignments == (OwnershipAssignment("items", 1, 2),)

    document["approved_at"] = "2026-10-29T12:00:00"
    plan_path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="timezone"):
        load_ownership_plan(plan_path)


def test_backfill_cli_requires_explicit_database_url(tmp_path):
    plan_path = tmp_path / "ownership.json"
    plan_path.write_text("{}", encoding="utf-8")
    env = os.environ.copy()
    env.pop("DATABASE_URL", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, "-B", "-m", "app.ownership_backfill", str(plan_path)],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode != 0
    assert "Set DATABASE_URL explicitly" in result.stderr
