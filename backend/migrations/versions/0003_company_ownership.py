"""Add nullable company ownership to warehouse records.

Revision ID: 0003_company_ownership
Revises: 0002_company_models
"""
from alembic import op

revision = "0003_company_ownership"
down_revision = "0002_company_models"
branch_labels = None
depends_on = None

# SQLite supports adding a nullable column with a REFERENCES clause without
# rebuilding the table. Existing rows and IDs remain untouched and NULL-owned.
SCHEMA_SQL = (
    """ALTER TABLE categories ADD COLUMN company_id INTEGER
REFERENCES companies (id)""",
    """CREATE INDEX ix_categories_company_id ON categories (company_id)""",
    """ALTER TABLE suppliers ADD COLUMN company_id INTEGER
REFERENCES companies (id)""",
    """CREATE INDEX ix_suppliers_company_id ON suppliers (company_id)""",
    """ALTER TABLE locations ADD COLUMN company_id INTEGER
REFERENCES companies (id)""",
    """CREATE INDEX ix_locations_company_id ON locations (company_id)""",
    """ALTER TABLE items ADD COLUMN company_id INTEGER
REFERENCES companies (id)""",
    """CREATE INDEX ix_items_company_id ON items (company_id)""",
    """ALTER TABLE transfers ADD COLUMN company_id INTEGER
REFERENCES companies (id)""",
    """CREATE INDEX ix_transfers_company_id ON transfers (company_id)""",
    """ALTER TABLE activity_logs ADD COLUMN company_id INTEGER
REFERENCES companies (id)""",
    """CREATE INDEX ix_activity_logs_company_id ON activity_logs (company_id)""",
)


def upgrade():
    for statement in SCHEMA_SQL:
        op.execute(statement)


def downgrade():
    raise RuntimeError(
        "Company-ownership downgrade is disabled; restore a verified backup instead"
    )
