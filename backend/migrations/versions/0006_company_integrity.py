"""Finalize company ownership and enforce cross-company integrity.

Revision ID: 0006_company_integrity
Revises: 0005_inventory_balances
"""
from alembic import op

revision = "0006_company_integrity"
down_revision = "0005_inventory_balances"
branch_labels = None
depends_on = None

OWNED_TABLES = (
    "categories", "suppliers", "locations", "items", "transfers", "activity_logs",
)


def _preflight(connection):
    unresolved = {
        table: connection.exec_driver_sql(
            f'SELECT count(*) FROM "{table}" WHERE company_id IS NULL'
        ).scalar_one()
        for table in OWNED_TABLES
    }
    unresolved = {table: count for table, count in unresolved.items() if count}
    if unresolved:
        details = ", ".join(f"{table}={count}" for table, count in unresolved.items())
        raise RuntimeError(
            "Unresolved legacy company ownership blocks migration: " + details
        )

    checks = {
        "item master-data ownership": """
            SELECT i.id FROM items i
            JOIN categories c ON c.id = i.category_id
            JOIN locations l ON l.id = i.location_id
            LEFT JOIN suppliers s ON s.id = i.supplier_id
            WHERE c.company_id != i.company_id OR l.company_id != i.company_id
               OR (i.supplier_id IS NOT NULL AND s.company_id != i.company_id)
            LIMIT 1
        """,
        "transfer ownership": """
            SELECT t.id FROM transfers t
            JOIN items i ON i.id = t.item_id
            JOIN locations source ON source.id = t.source_location_id
            JOIN locations destination ON destination.id = t.destination_location_id
            WHERE i.company_id != t.company_id
               OR source.company_id != t.company_id
               OR destination.company_id != t.company_id
            LIMIT 1
        """,
        "inventory-balance ownership": """
            SELECT b.id FROM inventory_balances b
            JOIN items i ON i.id = b.item_id
            JOIN locations l ON l.id = b.location_id
            WHERE i.company_id != b.company_id OR l.company_id != b.company_id
            LIMIT 1
        """,
        "negative item quantities": """
            SELECT id FROM items WHERE stock < 0 OR min_stock < 0 LIMIT 1
        """,
        "invalid transfer quantities": """
            SELECT id FROM transfers WHERE quantity <= 0 LIMIT 1
        """,
        "inventory totals": """
            SELECT i.id FROM items i
            LEFT JOIN inventory_balances b
              ON b.item_id = i.id AND b.company_id = i.company_id
            GROUP BY i.id, i.stock
            HAVING COALESCE(SUM(b.quantity), 0) != i.stock
            LIMIT 1
        """,
    }
    for label, statement in checks.items():
        if connection.exec_driver_sql(statement).first() is not None:
            raise RuntimeError(f"Company integrity preflight failed: {label}")


SCHEMA_SQL = (
    "CREATE TABLE _mt10_inventory_balances AS SELECT * FROM inventory_balances",
    "CREATE TABLE _mt10_transfers AS SELECT * FROM transfers",
    "CREATE TABLE _mt10_items AS SELECT * FROM items",
    "CREATE TABLE _mt10_activity_logs AS SELECT * FROM activity_logs",
    "CREATE TABLE _mt10_categories AS SELECT * FROM categories",
    "CREATE TABLE _mt10_suppliers AS SELECT * FROM suppliers",
    "CREATE TABLE _mt10_locations AS SELECT * FROM locations",
    "DROP TABLE inventory_balances",
    "DROP TABLE transfers",
    "DROP TABLE items",
    "DROP TABLE activity_logs",
    "DROP TABLE categories",
    "DROP TABLE suppliers",
    "DROP TABLE locations",
    """CREATE TABLE categories (
 id INTEGER NOT NULL, name VARCHAR(100) NOT NULL, description TEXT NOT NULL,
 icon VARCHAR(30) NOT NULL, color VARCHAR(20) NOT NULL, created_at DATETIME NOT NULL,
 company_id INTEGER NOT NULL, PRIMARY KEY (id),
 CONSTRAINT uq_categories_id_company UNIQUE (id, company_id),
 FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE RESTRICT
)""",
    """CREATE TABLE suppliers (
 id INTEGER NOT NULL, name VARCHAR(150) NOT NULL, contact_person VARCHAR(100) NOT NULL,
 email VARCHAR(255) NOT NULL, phone VARCHAR(30) NOT NULL, address VARCHAR(300) NOT NULL,
 category VARCHAR(100) NOT NULL, payment_terms VARCHAR(20) NOT NULL,
 is_active BOOLEAN NOT NULL, created_at DATETIME NOT NULL, company_id INTEGER NOT NULL,
 PRIMARY KEY (id), CONSTRAINT uq_suppliers_id_company UNIQUE (id, company_id),
 FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE RESTRICT
)""",
    """CREATE TABLE locations (
 id INTEGER NOT NULL, code VARCHAR(30) NOT NULL, name VARCHAR(120) NOT NULL,
 capacity INTEGER NOT NULL, created_at DATETIME NOT NULL, company_id INTEGER NOT NULL,
 PRIMARY KEY (id), CONSTRAINT uq_locations_id_company UNIQUE (id, company_id),
 FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE RESTRICT
)""",
    "INSERT INTO categories SELECT * FROM _mt10_categories",
    "INSERT INTO suppliers SELECT * FROM _mt10_suppliers",
    "INSERT INTO locations SELECT * FROM _mt10_locations",
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
 company_id INTEGER NOT NULL, PRIMARY KEY (id),
 CONSTRAINT uq_items_id_company UNIQUE (id, company_id),
 CONSTRAINT ck_items_stock CHECK (stock >= 0),
 CONSTRAINT ck_items_min_stock CHECK (min_stock >= 0),
 CONSTRAINT fk_items_category_company FOREIGN KEY(category_id, company_id)
  REFERENCES categories (id, company_id) ON DELETE RESTRICT,
 CONSTRAINT fk_items_supplier_company FOREIGN KEY(supplier_id, company_id)
  REFERENCES suppliers (id, company_id) ON DELETE RESTRICT,
 CONSTRAINT fk_items_location_company FOREIGN KEY(location_id, company_id)
  REFERENCES locations (id, company_id) ON DELETE RESTRICT,
 FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE RESTRICT
)""",
    "INSERT INTO items SELECT * FROM _mt10_items",
    "CREATE INDEX ix_items_name ON items (name)",
    "CREATE INDEX ix_items_sku ON items (sku)",
    "CREATE INDEX ix_items_company_id ON items (company_id)",
    "CREATE UNIQUE INDEX uq_items_company_sku ON items (company_id, sku) WHERE company_id IS NOT NULL",
    """CREATE TABLE transfers (
 id INTEGER NOT NULL, code VARCHAR(30) NOT NULL, item_id INTEGER NOT NULL,
 source_location_id INTEGER NOT NULL, destination_location_id INTEGER NOT NULL,
 quantity INTEGER NOT NULL, status VARCHAR(20) NOT NULL, priority VARCHAR(20) NOT NULL,
 notes TEXT NOT NULL, creator_id INTEGER NOT NULL, created_at DATETIME NOT NULL,
 updated_at DATETIME NOT NULL, company_id INTEGER NOT NULL, PRIMARY KEY (id),
 CONSTRAINT uq_transfers_company_code UNIQUE (company_id, code),
 CONSTRAINT ck_transfers_quantity CHECK (quantity > 0),
 CONSTRAINT fk_transfers_item_company FOREIGN KEY(item_id, company_id)
  REFERENCES items (id, company_id) ON DELETE RESTRICT,
 CONSTRAINT fk_transfers_source_location_company FOREIGN KEY(source_location_id, company_id)
  REFERENCES locations (id, company_id) ON DELETE RESTRICT,
 CONSTRAINT fk_transfers_destination_location_company FOREIGN KEY(destination_location_id, company_id)
  REFERENCES locations (id, company_id) ON DELETE RESTRICT,
 FOREIGN KEY(creator_id) REFERENCES users (id) ON DELETE RESTRICT,
 FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE RESTRICT
)""",
    "INSERT INTO transfers SELECT * FROM _mt10_transfers",
    "CREATE INDEX ix_transfers_code ON transfers (code)",
    "CREATE INDEX ix_transfers_company_id ON transfers (company_id)",
    """CREATE TABLE activity_logs (
 id INTEGER NOT NULL, user_id INTEGER, action VARCHAR(60) NOT NULL,
 entity_type VARCHAR(40) NOT NULL, entity_id VARCHAR(40), message VARCHAR(300) NOT NULL,
 created_at DATETIME NOT NULL, company_id INTEGER NOT NULL, PRIMARY KEY (id),
 FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL,
 FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE RESTRICT
)""",
    "INSERT INTO activity_logs SELECT * FROM _mt10_activity_logs",
    "CREATE INDEX ix_activity_logs_company_id ON activity_logs (company_id)",
    """CREATE TABLE inventory_balances (
 id INTEGER NOT NULL, company_id INTEGER NOT NULL, item_id INTEGER NOT NULL,
 location_id INTEGER NOT NULL, quantity INTEGER NOT NULL, reserved INTEGER NOT NULL,
 created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL, PRIMARY KEY (id),
 CONSTRAINT uq_inventory_balances_company_item_location UNIQUE (company_id, item_id, location_id),
 CONSTRAINT ck_inventory_balances_quantity CHECK (quantity >= 0),
 CONSTRAINT ck_inventory_balances_reserved CHECK (reserved >= 0),
 CONSTRAINT ck_inventory_balances_reserved_quantity CHECK (reserved <= quantity),
 CONSTRAINT fk_inventory_balances_item_company FOREIGN KEY(item_id, company_id)
  REFERENCES items (id, company_id) ON DELETE RESTRICT,
 CONSTRAINT fk_inventory_balances_location_company FOREIGN KEY(location_id, company_id)
  REFERENCES locations (id, company_id) ON DELETE RESTRICT,
 FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE RESTRICT
)""",
    "INSERT INTO inventory_balances SELECT * FROM _mt10_inventory_balances",
    "CREATE INDEX ix_inventory_balances_company_location ON inventory_balances (company_id, location_id)",
    "CREATE INDEX ix_inventory_balances_company_item ON inventory_balances (company_id, item_id)",
    "DROP TABLE _mt10_inventory_balances",
    "DROP TABLE _mt10_transfers",
    "DROP TABLE _mt10_items",
    "DROP TABLE _mt10_activity_logs",
    "DROP TABLE _mt10_categories",
    "DROP TABLE _mt10_suppliers",
    "DROP TABLE _mt10_locations",
)


def upgrade():
    connection = op.get_bind()
    _preflight(connection)
    for statement in SCHEMA_SQL:
        op.execute(statement)


def downgrade():
    raise RuntimeError(
        "Company-integrity downgrade is disabled; restore a verified backup instead"
    )
