"""Add explicit per-location inventory balances without legacy backfill.

Revision ID: 0005_inventory_balances
Revises: 0004_company_scoped_uniqueness
"""
from alembic import op

revision = "0005_inventory_balances"
down_revision = "0004_company_scoped_uniqueness"
branch_labels = None
depends_on = None

SCHEMA_SQL = (
    """CREATE TABLE inventory_balances (
 id INTEGER NOT NULL, company_id INTEGER NOT NULL, item_id INTEGER NOT NULL,
 location_id INTEGER NOT NULL, quantity INTEGER NOT NULL, reserved INTEGER NOT NULL,
 created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL, PRIMARY KEY (id),
 CONSTRAINT uq_inventory_balances_company_item_location UNIQUE (company_id, item_id, location_id),
 CONSTRAINT ck_inventory_balances_quantity CHECK (quantity >= 0),
 CONSTRAINT ck_inventory_balances_reserved CHECK (reserved >= 0),
 CONSTRAINT ck_inventory_balances_reserved_quantity CHECK (reserved <= quantity),
 FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE RESTRICT,
 FOREIGN KEY(item_id) REFERENCES items (id) ON DELETE RESTRICT,
 FOREIGN KEY(location_id) REFERENCES locations (id) ON DELETE RESTRICT
)""",
    "CREATE INDEX ix_inventory_balances_company_location ON inventory_balances (company_id, location_id)",
    "CREATE INDEX ix_inventory_balances_company_item ON inventory_balances (company_id, item_id)",
)


def upgrade():
    for statement in SCHEMA_SQL:
        op.execute(statement)


def downgrade():
    raise RuntimeError(
        "Inventory-balance downgrade is disabled; restore a verified backup instead"
    )
