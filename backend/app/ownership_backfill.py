"""Validated, explicit ownership registry backfill for the transition period."""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime
import json
import os
from pathlib import Path

from sqlalchemy.engine import Engine

from app.migration_support import INVENTORY_BALANCES, current_revision, validate_revision

OWNED_TABLES = (
    "categories",
    "suppliers",
    "locations",
    "items",
    "transfers",
    "activity_logs",
)


@dataclass(frozen=True)
class OwnershipAssignment:
    table: str
    row_id: int
    company_id: int


@dataclass(frozen=True)
class OwnershipPlan:
    approved_by: str
    approved_at: datetime
    reason: str
    assignments: tuple[OwnershipAssignment, ...]


@dataclass(frozen=True)
class BackfillResult:
    dry_run: bool
    rows_checked: int
    assignments_checked: int
    rows_updated: int
    balances_created: int


def _positive_integer(value, label):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def load_ownership_plan(path: str | Path) -> OwnershipPlan:
    """Load a human-approved JSON registry and reject unknown/ambiguous fields."""
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("Ownership plan must be a JSON object")
    expected_keys = {"approved_by", "approved_at", "reason", "assignments"}
    if set(document) != expected_keys:
        raise ValueError("Ownership plan fields must be: " + ", ".join(sorted(expected_keys)))
    if not isinstance(document["approved_by"], str) or not document["approved_by"].strip():
        raise ValueError("approved_by is required")
    if not isinstance(document["reason"], str) or not document["reason"].strip():
        raise ValueError("reason is required")
    try:
        approved_at = datetime.fromisoformat(document["approved_at"])
    except (TypeError, ValueError) as exc:
        raise ValueError("approved_at must be an ISO-8601 datetime") from exc
    if approved_at.tzinfo is None or approved_at.utcoffset() is None:
        raise ValueError("approved_at must include a timezone")
    raw_assignments = document["assignments"]
    if not isinstance(raw_assignments, list):
        raise ValueError("assignments must be a list")
    assignments = []
    for index, raw in enumerate(raw_assignments):
        if not isinstance(raw, dict) or set(raw) != {"table", "id", "company_id"}:
            raise ValueError(f"assignments[{index}] must contain table, id and company_id")
        if raw["table"] not in OWNED_TABLES:
            raise ValueError(f"assignments[{index}].table is not company-owned")
        assignments.append(OwnershipAssignment(
            table=raw["table"],
            row_id=_positive_integer(raw["id"], f"assignments[{index}].id"),
            company_id=_positive_integer(
                raw["company_id"], f"assignments[{index}].company_id"
            ),
        ))
    return OwnershipPlan(
        approved_by=document["approved_by"].strip(),
        approved_at=approved_at,
        reason=document["reason"].strip(),
        assignments=tuple(assignments),
    )


def _validate_plan(plan):
    if not isinstance(plan.approved_by, str) or not isinstance(plan.reason, str):
        raise ValueError("Ownership plan approval and reason must be text")
    if not plan.approved_by.strip() or not plan.reason.strip():
        raise ValueError("Ownership plan approval and reason are required")
    if not isinstance(plan.approved_at, datetime):
        raise ValueError("Ownership plan approval time must be a datetime")
    if plan.approved_at.tzinfo is None or plan.approved_at.utcoffset() is None:
        raise ValueError("Ownership plan approval time must include a timezone")
    for assignment in plan.assignments:
        if assignment.table not in OWNED_TABLES:
            raise ValueError(f"Unknown company-owned table: {assignment.table}")
        _positive_integer(assignment.row_id, f"{assignment.table}.id")
        _positive_integer(assignment.company_id, f"{assignment.table}.company_id")


def _effective_ownership(connection, plan):
    assignments = {}
    for assignment in plan.assignments:
        key = (assignment.table, assignment.row_id)
        if key in assignments:
            raise ValueError(f"Duplicate ownership assignment: {assignment.table}/{assignment.row_id}")
        assignments[key] = assignment.company_id

    company_ids = set(assignments.values())
    if company_ids:
        placeholders = ", ".join("?" for _ in company_ids)
        existing_companies = set(connection.exec_driver_sql(
            f"SELECT id FROM companies WHERE id IN ({placeholders})",
            tuple(sorted(company_ids)),
        ).scalars())
        missing = sorted(company_ids - existing_companies)
        if missing:
            raise ValueError("Unknown company IDs: " + ", ".join(map(str, missing)))

    effective = {}
    unresolved = []
    rows_checked = 0
    for table in OWNED_TABLES:
        rows = connection.exec_driver_sql(f'SELECT id, company_id FROM "{table}"').all()
        rows_checked += len(rows)
        known_ids = {row.id for row in rows}
        unknown_ids = sorted(
            row_id for assignment_table, row_id in assignments
            if assignment_table == table and row_id not in known_ids
        )
        if unknown_ids:
            raise ValueError(
                f"Unknown row IDs for {table}: " + ", ".join(map(str, unknown_ids))
            )
        for row in rows:
            assigned = assignments.get((table, row.id))
            if row.company_id is None:
                if assigned is None:
                    unresolved.append(f"{table}/{row.id}")
                    continue
                effective[(table, row.id)] = assigned
            else:
                if assigned is not None and assigned != row.company_id:
                    raise ValueError(
                        f"Conflicting ownership assignment for {table}/{row.id}"
                    )
                effective[(table, row.id)] = row.company_id
    if unresolved:
        raise ValueError("Unresolved ownership rows: " + ", ".join(unresolved))
    return assignments, effective, rows_checked


def _validate_relationship_graph(connection, effective):
    conflicts = []
    for row in connection.exec_driver_sql(
        "SELECT id, category_id, supplier_id, location_id FROM items"
    ).all():
        owner = effective[("items", row.id)]
        references = [
            ("categories", row.category_id),
            ("locations", row.location_id),
        ]
        if row.supplier_id is not None:
            references.append(("suppliers", row.supplier_id))
        for table, row_id in references:
            if effective.get((table, row_id)) != owner:
                conflicts.append(f"items/{row.id}->{table}/{row_id}")

    for row in connection.exec_driver_sql(
        "SELECT id, item_id, source_location_id, destination_location_id FROM transfers"
    ).all():
        owner = effective[("transfers", row.id)]
        for table, row_id in (
            ("items", row.item_id),
            ("locations", row.source_location_id),
            ("locations", row.destination_location_id),
        ):
            if effective.get((table, row_id)) != owner:
                conflicts.append(f"transfers/{row.id}->{table}/{row_id}")
    if conflicts:
        raise ValueError("Cross-company ownership relationships: " + ", ".join(conflicts))


def _balance_plan(connection, effective):
    """Validate existing ledger rows and plan deterministic item-location balances."""
    balances = connection.exec_driver_sql(
        "SELECT id, company_id, item_id, location_id, quantity, reserved "
        "FROM inventory_balances ORDER BY id"
    ).all()
    by_item = {}
    for balance in balances:
        item_owner = effective.get(("items", balance.item_id))
        location_owner = effective.get(("locations", balance.location_id))
        if item_owner != balance.company_id or location_owner != balance.company_id:
            raise ValueError(f"Cross-company inventory balance: {balance.id}")
        by_item.setdefault(balance.item_id, []).append(balance)

    missing = []
    for item in connection.exec_driver_sql(
        "SELECT id, location_id, stock FROM items ORDER BY id"
    ).all():
        existing = by_item.get(item.id, ())
        if existing:
            if sum(row.quantity for row in existing) != item.stock:
                raise ValueError(f"Inventory balance total differs from items/{item.id}.stock")
        else:
            missing.append((
                effective[("items", item.id)], item.id, item.location_id, item.stock,
            ))
    return missing


def run_ownership_backfill(
    engine: Engine,
    plan: OwnershipPlan,
    *,
    apply: bool = False,
) -> BackfillResult:
    """Validate the complete registry under a write lock; write only with apply=True."""
    if engine.dialect.name != "sqlite":
        raise RuntimeError("Ownership backfill currently supports SQLite only")
    with engine.connect() as connection:
        if connection.in_transaction():
            raise RuntimeError("Ownership backfill requires an idle connection")
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            _validate_plan(plan)
            revision = current_revision(connection)
            if revision != INVENTORY_BALANCES:
                raise RuntimeError(
                    "Ownership conversion must run at 0005_inventory_balances before "
                    "the final integrity migration"
                )
            validate_revision(connection, INVENTORY_BALANCES)
            assignments, effective, rows_checked = _effective_ownership(connection, plan)
            _validate_relationship_graph(connection, effective)
            missing_balances = _balance_plan(connection, effective)
            rows_updated = 0
            balances_created = 0
            if apply:
                for (table, row_id), company_id in sorted(assignments.items()):
                    result = connection.exec_driver_sql(
                        f'UPDATE "{table}" SET company_id = ? '
                        "WHERE id = ? AND company_id IS NULL",
                        (company_id, row_id),
                    )
                    rows_updated += result.rowcount
                for company_id, item_id, location_id, quantity in missing_balances:
                    connection.exec_driver_sql(
                        "INSERT INTO inventory_balances "
                        "(company_id, item_id, location_id, quantity, reserved, created_at, updated_at) "
                        "VALUES (?, ?, ?, ?, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                        (company_id, item_id, location_id, quantity),
                    )
                    balances_created += 1
                remaining = sum(
                    connection.exec_driver_sql(
                        f'SELECT count(*) FROM "{table}" WHERE company_id IS NULL'
                    ).scalar_one()
                    for table in OWNED_TABLES
                )
                if remaining:
                    raise RuntimeError("Ownership backfill left unresolved rows")
                if connection.exec_driver_sql("PRAGMA foreign_key_check").first() is not None:
                    raise RuntimeError("Ownership backfill violates foreign keys")
                connection.commit()
            else:
                connection.rollback()
            return BackfillResult(
                dry_run=not apply,
                rows_checked=rows_checked,
                assignments_checked=len(assignments),
                rows_updated=rows_updated,
                balances_created=balances_created,
            )
        except BaseException:
            connection.rollback()
            raise


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Validate an approved legacy ownership registry; dry-run by default."
    )
    parser.add_argument("plan", type=Path)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the fully validated registry in one transaction",
    )
    args = parser.parse_args(argv)
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        parser.error("Set DATABASE_URL explicitly; the backfill never uses the default database")

    from sqlalchemy.pool import NullPool
    from app.database import create_database_engine

    plan = load_ownership_plan(args.plan)
    engine = create_database_engine(database_url, poolclass=NullPool)
    try:
        result = run_ownership_backfill(engine, plan, apply=args.apply)
    finally:
        engine.dispose()
    print(json.dumps(asdict(result), sort_keys=True))


if __name__ == "__main__":
    main()
