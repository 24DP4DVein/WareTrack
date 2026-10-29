import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.database import Base, create_database_engine, initialize_database
from app.migration_support import BASELINE, current_revision, migration_config, upgrade_database, validate_baseline
from app.models import ActivityLog, Category, Item, Location, Supplier, Transfer, User

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture
def database_path(tmp_path):
    return tmp_path / "isolated.db"


@pytest.fixture
def file_engine(database_path):
    engine = create_database_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        yield engine
    finally:
        engine.dispose()


def create_legacy(engine):
    # Only this disposable fixture emulates the pre-Alembic create_all schema.
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([
            User(id=41, name="Original user", email="original@test.lv", password_hash="unchanged-hash", role="USER"),
            Category(id=51, name="Original category"),
            Location(id=61, code="SOURCE", name="Source"),
            Location(id=62, code="DEST", name="Destination"),
            Supplier(id=71, name="Original supplier", contact_person="Contact", email="supplier@test.lv", phone="1234567", address="Original address"),
        ])
        session.flush()
        session.add(Item(id=81, name="Original item", sku="ORIGINAL", category_id=51, supplier_id=71, location_id=61, stock=9, price=12.5))
        session.flush()
        session.add_all([
            Transfer(id=91, code="ORIGINAL-TRANSFER", item_id=81, source_location_id=61, destination_location_id=62, quantity=2, creator_id=41),
            ActivityLog(id=101, user_id=41, action="create", entity_type="item", entity_id="81", message="Original history"),
        ])
        session.commit()


def record_snapshot(engine):
    with engine.connect() as connection:
        return {
            name: connection.exec_driver_sql(f'SELECT * FROM "{name}" ORDER BY id').all()
            for name in Base.metadata.tables
        }


def test_empty_baseline_matches_current_models_and_upgrade_is_idempotent(file_engine):
    upgrade_database(file_engine)
    with file_engine.connect() as connection:
        assert current_revision(connection) == BASELINE
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        validate_baseline(connection)
    before = record_snapshot(file_engine)
    upgrade_database(file_engine)
    assert record_snapshot(file_engine) == before
    initialize_database(file_engine)


def test_verified_adoption_preserves_every_record_and_id(file_engine):
    create_legacy(file_engine)
    before = record_snapshot(file_engine)
    with pytest.raises(RuntimeError, match="explicitly requested"):
        upgrade_database(file_engine)
    assert "alembic_version" not in inspect(file_engine).get_table_names()
    upgrade_database(file_engine, adopt_existing=True)
    assert record_snapshot(file_engine) == before
    upgrade_database(file_engine, adopt_existing=True)
    assert record_snapshot(file_engine) == before
    initialize_database(file_engine)


def baseline_sql():
    return list(ScriptDirectory.from_config(migration_config()).get_revision(BASELINE).module.SCHEMA_SQL)


@pytest.mark.parametrize("change", [
    "missing_table", "extra_column", "column_type", "nullable", "default", "primary_key",
    "unique", "foreign_key", "foreign_key_action", "missing_index", "extra_index", "check", "view", "trigger",
])
def test_adoption_rejects_changed_schema_without_writes(database_path, file_engine, change):
    statements = baseline_sql()
    if change == "missing_table":
        statements = [sql for sql in statements if not sql.startswith("CREATE TABLE activity_logs")]
    elif change == "missing_index":
        statements = [sql for sql in statements if not sql.startswith("CREATE INDEX ix_items_name")]
    elif change in {"extra_index", "view", "trigger"}:
        statements.append({
            "extra_index": "CREATE INDEX unexpected_index ON users(name)",
            "view": "CREATE VIEW unexpected_view AS SELECT * FROM users",
            "trigger": "CREATE TRIGGER unexpected_trigger AFTER INSERT ON users BEGIN SELECT 1; END",
        }[change])
    else:
        replacements = {
            "extra_column": ("name VARCHAR(100) NOT NULL", "extra TEXT, name VARCHAR(100) NOT NULL"),
            "column_type": ("name VARCHAR(100) NOT NULL", "name VARCHAR(101) NOT NULL"),
            "nullable": ("name VARCHAR(100) NOT NULL", "name VARCHAR(100)"),
            "default": ("name VARCHAR(100) NOT NULL", "name VARCHAR(100) DEFAULT 'changed' NOT NULL"),
            "primary_key": ("PRIMARY KEY (id)", "PRIMARY KEY (id, name)"),
            "unique": ("UNIQUE (name)", "UNIQUE (name, description)"),
            "foreign_key": ("FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL", "CHECK (user_id > 0)"),
            "foreign_key_action": ("ON DELETE SET NULL", "ON DELETE RESTRICT"),
            "check": ("UNIQUE (name)", "UNIQUE (name), CHECK (id > 0)"),
        }
        old, new = replacements[change]
        for index, sql in enumerate(statements):
            if old in sql:
                statements[index] = sql.replace(old, new, 1)
                break
        else:
            raise AssertionError("Mutation did not change schema")
    with sqlite3.connect(database_path) as connection:
        for sql in statements:
            connection.execute(sql)
    before = database_path.read_bytes()
    with pytest.raises(RuntimeError, match="Incompatible database schema"):
        upgrade_database(file_engine, adopt_existing=True)
    file_engine.dispose()
    assert database_path.read_bytes() == before


def test_invalid_existing_foreign_keys_prevent_adoption(file_engine, database_path):
    create_legacy(file_engine)
    file_engine.dispose()
    with sqlite3.connect(database_path) as connection:
        connection.execute("UPDATE items SET category_id = 9999")
    before = database_path.read_bytes()
    with pytest.raises(RuntimeError, match="violates foreign keys"):
        upgrade_database(file_engine, adopt_existing=True)
    file_engine.dispose()
    assert database_path.read_bytes() == before


def test_startup_does_not_bootstrap_unmigrated_database(file_engine, database_path):
    with pytest.raises(RuntimeError, match="not migrated"):
        initialize_database(file_engine)
    assert not database_path.exists()
    create_legacy(file_engine)
    before = database_path.read_bytes()
    with pytest.raises(RuntimeError, match="not migrated"):
        initialize_database(file_engine)
    file_engine.dispose()
    assert database_path.read_bytes() == before


def test_unknown_revision_and_schema_drift_are_rejected(file_engine):
    upgrade_database(file_engine)
    with file_engine.begin() as connection:
        connection.exec_driver_sql("UPDATE alembic_version SET version_num = 'unknown'")
    with pytest.raises(RuntimeError, match="Unknown"):
        upgrade_database(file_engine)
    with pytest.raises(RuntimeError, match="Unknown"):
        initialize_database(file_engine)
    with file_engine.begin() as connection:
        connection.exec_driver_sql("UPDATE alembic_version SET version_num = '0001_baseline'")
        connection.exec_driver_sql("DROP INDEX ix_items_name")
    with pytest.raises(RuntimeError, match="Incompatible"):
        upgrade_database(file_engine)
    with pytest.raises(RuntimeError, match="Incompatible"):
        initialize_database(file_engine)


def test_blind_stamp_and_baseline_downgrade_are_disabled(file_engine):
    with file_engine.connect() as connection:
        with pytest.raises(RuntimeError, match="stamp is disabled"):
            command.stamp(migration_config(connection), "head")
    assert inspect(file_engine).get_table_names() == []
    upgrade_database(file_engine)
    with file_engine.connect() as connection:
        with pytest.raises(RuntimeError, match="downgrade is disabled"):
            command.downgrade(migration_config(connection), "base")
    initialize_database(file_engine)


def test_sqlite_ddl_failure_rolls_back_version_and_schema(file_engine):
    from sqlalchemy import event

    def fail_after_some_ddl(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("CREATE TABLE users"):
            raise RuntimeError("simulated migration failure")

    event.listen(file_engine, "before_cursor_execute", fail_after_some_ddl)
    try:
        with pytest.raises(RuntimeError, match="simulated"):
            upgrade_database(file_engine)
    finally:
        event.remove(file_engine, "before_cursor_execute", fail_after_some_ddl)
    assert inspect(file_engine).get_table_names() == []
    upgrade_database(file_engine)
    initialize_database(file_engine)


def test_cli_requires_explicit_url_and_supports_percent_in_path(tmp_path):
    env = os.environ.copy()
    env.pop("DATABASE_URL", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    args = [sys.executable, "-B", "-m", "alembic", "-c", str(BACKEND / "alembic.ini")]
    result = subprocess.run(args + ["upgrade", "head"], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode != 0 and "Set DATABASE_URL explicitly" in result.stderr
    database = tmp_path / "safe%test.db"
    env["DATABASE_URL"] = f"sqlite:///{database.as_posix()}"
    for operation in (["upgrade", "head"], ["current"], ["check"]):
        result = subprocess.run(args + operation, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stdout + result.stderr
        if operation == ["current"]:
            assert BASELINE in result.stdout


def test_documented_cli_adoption_preserves_legacy_records(file_engine, database_path):
    create_legacy(file_engine)
    before = record_snapshot(file_engine)
    file_engine.dispose()
    env = os.environ.copy()
    env.update(DATABASE_URL=f"sqlite:///{database_path.as_posix()}", PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run(
        [sys.executable, "-B", "-m", "alembic", "-c", str(BACKEND / "alembic.ini"),
         "-x", "adopt_existing=true", "upgrade", "head"],
        cwd=database_path.parent, env=env, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert record_snapshot(file_engine) == before
    initialize_database(file_engine)
