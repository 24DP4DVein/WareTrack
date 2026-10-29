import os
from pathlib import Path

from sqlalchemy import create_engine, event, inspect
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
    """Bootstrap empty SQLite only; never repair or migrate an existing schema."""
    # Ensure metadata is populated even when called outside app.main.
    from app import models  # noqa: F401

    with db_engine.begin() as connection:
        inspector = inspect(connection)
        tables = set(inspector.get_table_names())
        views = inspector.get_view_names()
        if not tables and not views and db_engine.dialect.name == "sqlite":
            Base.metadata.create_all(bind=connection)
            return
        missing = set(Base.metadata.tables) - tables
        if missing:
            raise RuntimeError(
                "Database schema is incomplete; explicit schema setup/migration is required. "
                f"Missing tables: {', '.join(sorted(missing))}"
            )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

