"""Scope warehouse uniqueness to a non-null company.

Revision ID: 0004_company_scoped_uniqueness
Revises: 0003_company_ownership
"""
from alembic import op

revision = "0004_company_scoped_uniqueness"
down_revision = "0003_company_ownership"
branch_labels = None
depends_on = None

# SQLite cannot drop anonymous UNIQUE constraints. Copying rows into plain
# backup tables lets us rebuild the dependency chain leaf-first while foreign
# keys remain enabled. Column order stays compatible with revision 0003.
SCHEMA_SQL = (
    "CREATE TABLE _mt06_transfers AS SELECT * FROM transfers",
    "CREATE TABLE _mt06_items AS SELECT * FROM items",
    "CREATE TABLE _mt06_categories AS SELECT * FROM categories",
    "CREATE TABLE _mt06_suppliers AS SELECT * FROM suppliers",
    "CREATE TABLE _mt06_locations AS SELECT * FROM locations",
    "DROP TABLE transfers",
    "DROP TABLE items",
    "DROP TABLE categories",
    "DROP TABLE suppliers",
    "DROP TABLE locations",
    """CREATE TABLE categories (
 id INTEGER NOT NULL, name VARCHAR(100) NOT NULL, description TEXT NOT NULL,
 icon VARCHAR(30) NOT NULL, color VARCHAR(20) NOT NULL, created_at DATETIME NOT NULL,
 company_id INTEGER, PRIMARY KEY (id), FOREIGN KEY(company_id) REFERENCES companies (id)
)""",
    """CREATE TABLE suppliers (
 id INTEGER NOT NULL, name VARCHAR(150) NOT NULL, contact_person VARCHAR(100) NOT NULL,
 email VARCHAR(255) NOT NULL, phone VARCHAR(30) NOT NULL, address VARCHAR(300) NOT NULL,
 category VARCHAR(100) NOT NULL, payment_terms VARCHAR(20) NOT NULL,
 is_active BOOLEAN NOT NULL, created_at DATETIME NOT NULL, company_id INTEGER,
 PRIMARY KEY (id), FOREIGN KEY(company_id) REFERENCES companies (id)
)""",
    """CREATE TABLE locations (
 id INTEGER NOT NULL, code VARCHAR(30) NOT NULL, name VARCHAR(120) NOT NULL,
 capacity INTEGER NOT NULL, created_at DATETIME NOT NULL, company_id INTEGER,
 PRIMARY KEY (id), FOREIGN KEY(company_id) REFERENCES companies (id)
)""",
    "INSERT INTO categories SELECT * FROM _mt06_categories",
    "INSERT INTO suppliers SELECT * FROM _mt06_suppliers",
    "INSERT INTO locations SELECT * FROM _mt06_locations",
    "CREATE INDEX ix_categories_company_id ON categories (company_id)",
    "CREATE UNIQUE INDEX uq_categories_company_name ON categories (company_id, name) WHERE company_id IS NOT NULL",
    "CREATE INDEX ix_suppliers_company_id ON suppliers (company_id)",
    "CREATE UNIQUE INDEX uq_suppliers_company_name ON suppliers (company_id, name) WHERE company_id IS NOT NULL",
    "CREATE UNIQUE INDEX uq_suppliers_company_email ON suppliers (company_id, email) WHERE company_id IS NOT NULL",
    "CREATE INDEX ix_locations_company_id ON locations (company_id)",
    "CREATE UNIQUE INDEX uq_locations_company_code ON locations (company_id, code) WHERE company_id IS NOT NULL",
    """CREATE TABLE items (
 id INTEGER NOT NULL, name VARCHAR(100) NOT NULL, sku VARCHAR(30) NOT NULL,
 category_id INTEGER NOT NULL, supplier_id INTEGER, location_id INTEGER NOT NULL,
 stock INTEGER NOT NULL, min_stock INTEGER NOT NULL, price FLOAT NOT NULL,
 description TEXT NOT NULL, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL,
 company_id INTEGER, PRIMARY KEY (id),
 FOREIGN KEY(category_id) REFERENCES categories (id) ON DELETE RESTRICT,
 FOREIGN KEY(supplier_id) REFERENCES suppliers (id) ON DELETE SET NULL,
 FOREIGN KEY(location_id) REFERENCES locations (id) ON DELETE RESTRICT,
 FOREIGN KEY(company_id) REFERENCES companies (id)
)""",
    "INSERT INTO items SELECT * FROM _mt06_items",
    "CREATE INDEX ix_items_name ON items (name)",
    "CREATE INDEX ix_items_sku ON items (sku)",
    "CREATE INDEX ix_items_company_id ON items (company_id)",
    "CREATE UNIQUE INDEX uq_items_company_sku ON items (company_id, sku) WHERE company_id IS NOT NULL",
    """CREATE TABLE transfers (
 id INTEGER NOT NULL, code VARCHAR(30) NOT NULL, item_id INTEGER NOT NULL,
 source_location_id INTEGER NOT NULL, destination_location_id INTEGER NOT NULL,
 quantity INTEGER NOT NULL, status VARCHAR(20) NOT NULL, priority VARCHAR(20) NOT NULL,
 notes TEXT NOT NULL, creator_id INTEGER NOT NULL, created_at DATETIME NOT NULL,
 updated_at DATETIME NOT NULL, company_id INTEGER, PRIMARY KEY (id), UNIQUE (code),
 FOREIGN KEY(item_id) REFERENCES items (id) ON DELETE RESTRICT,
 FOREIGN KEY(source_location_id) REFERENCES locations (id) ON DELETE RESTRICT,
 FOREIGN KEY(destination_location_id) REFERENCES locations (id) ON DELETE RESTRICT,
 FOREIGN KEY(creator_id) REFERENCES users (id) ON DELETE RESTRICT,
 FOREIGN KEY(company_id) REFERENCES companies (id)
)""",
    "INSERT INTO transfers SELECT * FROM _mt06_transfers",
    "CREATE INDEX ix_transfers_code ON transfers (code)",
    "CREATE INDEX ix_transfers_company_id ON transfers (company_id)",
    "DROP TABLE _mt06_transfers",
    "DROP TABLE _mt06_items",
    "DROP TABLE _mt06_categories",
    "DROP TABLE _mt06_suppliers",
    "DROP TABLE _mt06_locations",
)


def upgrade():
    for statement in SCHEMA_SQL:
        op.execute(statement)


def downgrade():
    raise RuntimeError(
        "Company-scoped uniqueness downgrade is disabled; restore a verified backup instead"
    )
