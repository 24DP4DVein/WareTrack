"""Add companies, memberships and join-request history.

Revision ID: 0002_company_models
Revises: 0001_baseline
"""
from alembic import op

revision = "0002_company_models"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None

# Frozen SQLite DDL. Keep this revision independent of future ORM changes.
SCHEMA_SQL = (
    """CREATE TABLE companies (
	id INTEGER NOT NULL,
	name VARCHAR(150) NOT NULL,
	slug VARCHAR(100) NOT NULL,
	is_active BOOLEAN NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (slug)
)""",
    """CREATE INDEX ix_companies_active_name ON companies (is_active, name)""",
    """CREATE TABLE company_memberships (
	id INTEGER NOT NULL,
	company_id INTEGER NOT NULL,
	user_id INTEGER NOT NULL,
	role VARCHAR(20) NOT NULL,
	is_active BOOLEAN NOT NULL,
	approved_at DATETIME,
	approved_by_id INTEGER,
	revoked_at DATETIME,
	revoked_by_id INTEGER,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_company_memberships_company_user UNIQUE (company_id, user_id),
	CONSTRAINT ck_company_memberships_role CHECK (role IN ('LIETOTAJS', 'VADITAJS')),
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE RESTRICT,
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE RESTRICT,
	FOREIGN KEY(approved_by_id) REFERENCES users (id) ON DELETE SET NULL,
	FOREIGN KEY(revoked_by_id) REFERENCES users (id) ON DELETE SET NULL
)""",
    """CREATE INDEX ix_company_memberships_company_active_role
ON company_memberships (company_id, is_active, role)""",
    """CREATE INDEX ix_company_memberships_user_active
ON company_memberships (user_id, is_active)""",
    """CREATE TABLE company_join_requests (
	id INTEGER NOT NULL,
	company_id INTEGER NOT NULL,
	user_id INTEGER NOT NULL,
	status VARCHAR(20) NOT NULL,
	requested_at DATETIME NOT NULL,
	reviewed_at DATETIME,
	reviewed_by_id INTEGER,
	rejection_reason TEXT,
	PRIMARY KEY (id),
	CONSTRAINT ck_company_join_requests_status
		CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED')),
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE RESTRICT,
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE RESTRICT,
	FOREIGN KEY(reviewed_by_id) REFERENCES users (id) ON DELETE SET NULL
)""",
    """CREATE INDEX ix_company_join_requests_company_status_requested
ON company_join_requests (company_id, status, requested_at)""",
    """CREATE INDEX ix_company_join_requests_user_status_requested
ON company_join_requests (user_id, status, requested_at)""",
    """CREATE UNIQUE INDEX uq_company_join_requests_pending
ON company_join_requests (company_id, user_id) WHERE status = 'PENDING'""",
)


def upgrade():
    for statement in SCHEMA_SQL:
        op.execute(statement)


def downgrade():
    raise RuntimeError(
        "Company-model downgrade is disabled; restore a verified backup instead"
    )
