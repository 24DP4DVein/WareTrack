import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.database import create_database_engine, engine, get_db, initialize_database
from app.main import app


BACKEND = Path(__file__).resolve().parents[1]


def run_python(source, database_url, *args):
    env = os.environ.copy()
    env.update(DATABASE_URL=database_url, PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run(
        [sys.executable, "-B", "-c", source, *map(str, args)],
        cwd=BACKEND, env=env, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_import_does_not_connect_or_create_database(tmp_path):
    database = tmp_path / "must-not-exist.db"
    run_python(
        """
from sqlalchemy import event
from sqlalchemy.engine import Engine
@event.listens_for(Engine, 'engine_connect')
def forbid_connection(*args):
    raise AssertionError('Import opened a database connection')
import app.database
import app.routers
import app.main
""",
        f"sqlite:///{database.as_posix()}",
    )
    assert not database.exists()


def test_normal_lifespan_after_explicit_development_migration(tmp_path):
    database = tmp_path / "development.db"
    run_python(
        """
from pathlib import Path
import sys
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from app.database import Base, engine
from app.main import app
from app.migration_support import upgrade_database
assert not Path(sys.argv[1]).exists()
upgrade_database(engine)
with TestClient(app) as client:
    assert client.get('/api/health').status_code == 200
    assert client.get('/api/items').status_code == 410
    assert set(inspect(engine).get_table_names()) == set(Base.metadata.tables) | {'alembic_version'}
    response = client.post('/api/auth/register', json={
        'name': 'Startup test', 'email': 'startup@test.lv',
        'password': 'Password123!', 'passwordConfirmation': 'Password123!',
    })
    assert response.status_code == 201
    assert response.json()['user']['role'] == 'USER'
engine.dispose()
""",
        f"sqlite:///{database.as_posix()}", database,
    )
    assert database.exists()
    before = database.read_bytes()
    run_python(
        """
from fastapi.testclient import TestClient
from app.main import app
from app.database import engine
with TestClient(app) as client:
    assert client.post('/api/auth/login', json={
        'email': 'startup@test.lv', 'password': 'Password123!',
    }).status_code == 200
engine.dispose()
""",
        f"sqlite:///{database.as_posix()}",
    )
    assert database.read_bytes() == before


def test_existing_incomplete_database_is_not_repaired(tmp_path):
    database = tmp_path / "existing.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE sentinel (value TEXT)")
        connection.execute("INSERT INTO sentinel VALUES ('preserve me')")
    before = database.read_bytes()
    isolated_engine = create_database_engine(f"sqlite:///{database.as_posix()}")
    try:
        with pytest.raises(RuntimeError, match="explicit schema setup/migration"):
            initialize_database(isolated_engine)
        assert inspect(isolated_engine).get_table_names() == ["sentinel"]
    finally:
        isolated_engine.dispose()
    assert database.read_bytes() == before


def test_foreign_keys_are_enforced(test_engine):
    with test_engine.connect() as connection:
        assert connection.scalar(text("PRAGMA foreign_keys")) == 1
        with pytest.raises(IntegrityError):
            connection.execute(text(
                "INSERT INTO activity_logs "
                "(user_id, action, entity_type, message, created_at) "
                "VALUES (99999, 'test', 'test', 'invalid user', CURRENT_TIMESTAMP)"
            ))
        connection.rollback()


@pytest.mark.parametrize("iteration", [1, 2])
def test_each_client_gets_fresh_database(client, test_engine, iteration):
    assert app.state.database_engine is test_engine
    assert test_engine is not engine
    assert test_engine.url.database in (None, "", ":memory:")
    assert client.get("/api/items").status_code == 410
    with test_engine.begin() as connection:
        connection.execute(text("DELETE FROM items"))
    assert client.get("/api/items").status_code == 410


def test_client_teardown_restores_overrides_and_lifespan_engine(test_engine):
    # Exercise the fixture's finally block, including an exception in the body.
    from conftest import client as client_fixture, fresh_database

    sessions = fresh_database.__wrapped__(test_engine)
    previous = app.dependency_overrides.copy()
    fixture = client_fixture.__wrapped__(sessions, test_engine)
    next(fixture)
    assert get_db in app.dependency_overrides
    with pytest.raises(RuntimeError, match="simulated test failure"):
        fixture.throw(RuntimeError("simulated test failure"))
    assert app.dependency_overrides == previous
    assert app.state.database_engine is engine


def test_test_setup_replaces_inherited_database_url_without_touching_it(tmp_path):
    # This is a disposable sentinel, never an actual production/staging path.
    database = tmp_path / "production-sentinel.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE sentinel (value TEXT)")
        connection.execute("INSERT INTO sentinel VALUES ('unchanged')")
    before = database.read_bytes()
    run_python(
        """
import runpy
namespace = runpy.run_path('tests/conftest.py')
import app.database
assert app.database.DATABASE_URL == 'sqlite://'
database_fixture = namespace['test_engine'].__wrapped__()
test_engine = next(database_fixture)
try:
    sessions = namespace['fresh_database'].__wrapped__(test_engine)
    client_fixture = namespace['client'].__wrapped__(sessions, test_engine)
    client = next(client_fixture)
    try:
        assert client.get('/api/items').status_code == 410
    finally:
        client_fixture.close()
finally:
    database_fixture.close()
""",
        f"sqlite:///{database.as_posix()}",
    )
    assert database.read_bytes() == before


def test_test_setup_rejects_early_application_import():
    run_python(
        """
import runpy
import pytest
import app.database
try:
    runpy.run_path('tests/conftest.py')
except pytest.UsageError:
    pass
else:
    raise AssertionError('Unsafe import order was accepted')
""",
        "sqlite://",
    )
