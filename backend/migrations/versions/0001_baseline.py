"""Existing WareTrack SQLite schema, without companies.

The SQL snapshot is intentionally independent of future ORM changes.
"""
from alembic import op
from sqlalchemy import inspect

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None

# Frozen SQLite DDL; never regenerate this revision after release.
SCHEMA_SQL = (
    """CREATE TABLE categories (
	id INTEGER NOT NULL,
	name VARCHAR(100) NOT NULL,
	description TEXT NOT NULL,
	icon VARCHAR(30) NOT NULL,
	color VARCHAR(20) NOT NULL,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (name)
)""",
    """CREATE TABLE locations (
	id INTEGER NOT NULL,
	code VARCHAR(30) NOT NULL,
	name VARCHAR(120) NOT NULL,
	capacity INTEGER NOT NULL,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (code)
)""",
    """CREATE TABLE suppliers (
	id INTEGER NOT NULL,
	name VARCHAR(150) NOT NULL,
	contact_person VARCHAR(100) NOT NULL,
	email VARCHAR(255) NOT NULL,
	phone VARCHAR(30) NOT NULL,
	address VARCHAR(300) NOT NULL,
	category VARCHAR(100) NOT NULL,
	payment_terms VARCHAR(20) NOT NULL,
	is_active BOOLEAN NOT NULL,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (name),
	UNIQUE (email)
)""",
    """CREATE TABLE users (
	id INTEGER NOT NULL,
	name VARCHAR(100) NOT NULL,
	email VARCHAR(255) NOT NULL,
	password_hash VARCHAR(255) NOT NULL,
	role VARCHAR(20) NOT NULL,
	is_active BOOLEAN NOT NULL,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id)
)""",
    """CREATE UNIQUE INDEX ix_users_email ON users (email)""",
    """CREATE TABLE activity_logs (
	id INTEGER NOT NULL,
	user_id INTEGER,
	action VARCHAR(60) NOT NULL,
	entity_type VARCHAR(40) NOT NULL,
	entity_id VARCHAR(40),
	message VARCHAR(300) NOT NULL,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
)""",
    """CREATE TABLE items (
	id INTEGER NOT NULL,
	name VARCHAR(100) NOT NULL,
	sku VARCHAR(30) NOT NULL,
	category_id INTEGER NOT NULL,
	supplier_id INTEGER,
	location_id INTEGER NOT NULL,
	stock INTEGER NOT NULL,
	min_stock INTEGER NOT NULL,
	price FLOAT NOT NULL,
	description TEXT NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(category_id) REFERENCES categories (id) ON DELETE RESTRICT,
	FOREIGN KEY(supplier_id) REFERENCES suppliers (id) ON DELETE SET NULL,
	FOREIGN KEY(location_id) REFERENCES locations (id) ON DELETE RESTRICT
)""",
    """CREATE INDEX ix_items_name ON items (name)""",
    """CREATE UNIQUE INDEX ix_items_sku ON items (sku)""",
    """CREATE TABLE transfers (
	id INTEGER NOT NULL,
	code VARCHAR(30) NOT NULL,
	item_id INTEGER NOT NULL,
	source_location_id INTEGER NOT NULL,
	destination_location_id INTEGER NOT NULL,
	quantity INTEGER NOT NULL,
	status VARCHAR(20) NOT NULL,
	priority VARCHAR(20) NOT NULL,
	notes TEXT NOT NULL,
	creator_id INTEGER NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (code),
	FOREIGN KEY(item_id) REFERENCES items (id) ON DELETE RESTRICT,
	FOREIGN KEY(source_location_id) REFERENCES locations (id) ON DELETE RESTRICT,
	FOREIGN KEY(destination_location_id) REFERENCES locations (id) ON DELETE RESTRICT,
	FOREIGN KEY(creator_id) REFERENCES users (id) ON DELETE RESTRICT
)""",
    """CREATE INDEX ix_transfers_code ON transfers (code)""",
)


def upgrade():
    connection = op.get_bind()
    if inspect(connection).has_table("users"):
        from app.migration_support import validate_baseline
        validate_baseline(connection)
        return  # Verified adoption: only Alembic's revision row will be added.
    for statement in SCHEMA_SQL:
        op.execute(statement)


def downgrade():
    raise RuntimeError("Baseline downgrade is disabled; restore a verified backup instead")
