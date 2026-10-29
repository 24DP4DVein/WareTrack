import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DEFAULT_DB = Path(__file__).resolve().parents[1] / "waretrack.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB.as_posix()}")


def create_database_engine(url: str, **kwargs) -> Engine:
    """Configure an engine without opening a connection."""
    is_sqlite = make_url(url).get_backend_name() == "sqlite"
    db_engine = create_engine(url, connect_args={"check_same_thread": False} if is_sqlite else {}, **kwargs)
    if is_sqlite:
        @event.listens_for(db_engine, "connect")
        def enable_sqlite_foreign_keys(dbapi_connection, _):
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA foreign_keys=ON")
            finally:
                cursor.close()
    return db_engine


engine = create_database_engine(DATABASE_URL)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def initialize_database(db_engine: Engine) -> None:
    """Validate readiness at startup; never create, migrate or stamp tables."""
    from app.migration_support import require_migrated_database

    # Avoid even creating an empty SQLite file when bootstrap was forgotten.
    if db_engine.dialect.name == "sqlite":
        database = db_engine.url.database
        if database and database != ":memory:" and not db_engine.url.query.get("uri"):
            if not Path(database).is_file():
                raise RuntimeError("Database is not migrated; explicit schema setup/migration with Alembic is required")
    with db_engine.connect() as connection:
        require_migrated_database(connection)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

