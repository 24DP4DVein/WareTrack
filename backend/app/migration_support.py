"""Explicit migration helpers and conservative SQLite baseline verification."""
from functools import lru_cache
from pathlib import Path
import re
import sqlite3

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND = Path(__file__).resolve().parents[1]
BASELINE = "0001_baseline"
COMPANY_MODELS = "0002_company_models"
COMPANY_OWNERSHIP = "0003_company_ownership"
COMPANY_SCOPED_UNIQUENESS = "0004_company_scoped_uniqueness"
HEAD = "0005_inventory_balances"
REVISION_ORDER = (
    BASELINE, COMPANY_MODELS, COMPANY_OWNERSHIP,
    COMPANY_SCOPED_UNIQUENESS, HEAD,
)
KNOWN_REVISIONS = set(REVISION_ORDER)


def migration_config(connection=None, *, adopt_existing=False):
    config = Config(str(BACKEND / "alembic.ini"))
    if connection is not None:
        config.attributes["connection"] = connection
    config.attributes["adopt_existing"] = adopt_existing
    return config


def upgrade_database(db_engine, *, adopt_existing=False):
    """Explicit operation. Startup must never call this function."""
    with db_engine.connect() as connection:
        command.upgrade(migration_config(connection, adopt_existing=adopt_existing), "head")


def sql_tokens(sql):
    # Ignore formatting outside literals, not changes to defaults or quoted names.
    return tuple(re.findall(r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|`[^`]*`|\[[^\]]*\]|[\w]+|[^\s]", sql or ""))


def schema_signature(rows):
    return {
        (kind, name, table): sql_tokens(sql)
        for kind, name, table, sql in rows
        if table != "alembic_version" and name != "sqlite_sequence"
    }


@lru_cache(maxsize=len(KNOWN_REVISIONS))
def revision_signature(revision):
    if revision not in KNOWN_REVISIONS:
        raise RuntimeError("Unknown or incomplete Alembic revision; explicit migration review required")
    scripts = ScriptDirectory.from_config(migration_config())
    with sqlite3.connect(":memory:") as reference:
        for revision_id in REVISION_ORDER:
            for statement in scripts.get_revision(revision_id).module.SCHEMA_SQL:
                reference.execute(statement)
            if revision_id == revision:
                break
        return schema_signature(reference.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master"
        ).fetchall())


def validate_revision(connection, revision):
    """Fail closed on any DDL difference, including extra views/triggers/indexes.

    Comparing SQLite's complete DDL also checks column order/type/nullability,
    defaults, PK/UNIQUE/CHECK, FK actions, collations and index definitions.
    Equivalent but differently declared schemas require manual review.
    """
    if connection.dialect.name != "sqlite":
        raise RuntimeError("This baseline supports SQLite only")
    rows = connection.exec_driver_sql("SELECT type, name, tbl_name, sql FROM sqlite_master").all()
    actual, expected = schema_signature(rows), revision_signature(revision)
    if actual != expected:
        changed = sorted(key[1] for key in actual.keys() | expected.keys() if actual.get(key) != expected.get(key))
        raise RuntimeError("Incompatible database schema: " + ", ".join(changed))
    if connection.exec_driver_sql("PRAGMA integrity_check").scalars().all() != ["ok"]:
        raise RuntimeError("SQLite integrity check failed")
    if connection.exec_driver_sql("PRAGMA foreign_key_check").first() is not None:
        raise RuntimeError("Existing data violates foreign keys")


def validate_baseline(connection):
    """Verify an unversioned legacy database before baseline adoption."""
    validate_revision(connection, BASELINE)


def current_revision(connection):
    rows = connection.exec_driver_sql(
        "SELECT type, name, sql FROM sqlite_master WHERE tbl_name = 'alembic_version'"
    ).all()
    expected = sql_tokens(
        "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL, "
        "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
    )
    tables = [sql for kind, name, sql in rows if kind == "table" and name == "alembic_version"]
    if not tables:
        return None
    expected_objects = {("table", "alembic_version"), ("index", "sqlite_autoindex_alembic_version_1")}
    if (len(tables) != 1 or sql_tokens(tables[0]) != expected
            or {(kind, name) for kind, name, _ in rows} != expected_objects
            or any(sql is not None for kind, _, sql in rows if kind == "index")):
        raise RuntimeError("Invalid Alembic version table")
    revisions = connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalars().all()
    if len(revisions) != 1 or revisions[0] not in KNOWN_REVISIONS:
        raise RuntimeError("Unknown or incomplete Alembic revision; explicit migration review required")
    return revisions[0]


def require_migrated_database(connection):
    if current_revision(connection) != HEAD:
        raise RuntimeError("Database is not migrated; explicit schema setup/migration with Alembic is required")
    validate_revision(connection, HEAD)
