import os

from alembic import context
from sqlalchemy.pool import NullPool

from app.database import Base, DATABASE_URL, create_database_engine
from app import models  # Register every ORM table before target_metadata.
from app.migration_support import current_revision, validate_baseline

config = context.config
target_metadata = Base.metadata


def reject_stamp(*, step, **kwargs):
    if step.is_stamp:
        raise RuntimeError("Blind stamp is disabled; use verified adoption via upgrade")


def run(connection):
    if connection.dialect.name != "sqlite":
        raise RuntimeError("This migration baseline supports SQLite only")
    if connection.in_transaction():
        raise RuntimeError("Pass an idle connection; migrations own their transaction")
    # Explicit BEGIN makes SQLite DDL and the revision update atomic even with
    # sqlite3 legacy transaction control. It also prevents an adoption race.
    connection.exec_driver_sql("BEGIN IMMEDIATE")
    try:
        revision = current_revision(connection)
        objects = connection.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE name NOT GLOB 'sqlite_*' "
            "AND tbl_name != 'alembic_version'"
        ).all()
        if revision is not None:
            validate_baseline(connection)
        elif objects:
            if not (config.attributes.get("adopt_existing") or context.get_x_argument(as_dictionary=True).get("adopt_existing") == "true"):
                raise RuntimeError("Unversioned existing database: verified adoption must be explicitly requested")
            validate_baseline(connection)
        context.configure(
            connection=connection, target_metadata=target_metadata,
            render_as_batch=True, compare_type=True, compare_server_default=True,
            transactional_ddl=True, on_version_apply=reject_stamp,
        )
        with context.begin_transaction():
            context.run_migrations()
        connection.commit()
    except BaseException:
        connection.rollback()
        raise


if context.is_offline_mode():
    raise RuntimeError("Offline SQL is disabled: schema verification requires an online connection")

connection = config.attributes.get("connection")
if connection is not None:
    run(connection)
else:
    if not os.environ.get("DATABASE_URL"):
        raise RuntimeError("Set DATABASE_URL explicitly; migrations never default to the normal database")
    migration_engine = create_database_engine(DATABASE_URL, poolclass=NullPool)
    try:
        with migration_engine.connect() as connection:
            run(connection)
    finally:
        migration_engine.dispose()
