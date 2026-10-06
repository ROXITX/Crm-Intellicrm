"""full-text search indexes

Revision ID: 0003
Revises: 0002
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

# Expressions must match app/api/misc.py::fts() exactly for the planner to use the indexes.
INDEXES = {
    "leads": "coalesce(name,'') || ' ' || coalesce(company_name,'') || ' ' || coalesce(email,'')",
    "customers": "coalesce(name,'') || ' ' || coalesce(company_name,'') || ' ' || coalesce(email,'')",
    "projects": "coalesce(name,'') || ' ' || coalesce(description,'')",
    "tasks": "coalesce(title,'') || ' ' || coalesce(description,'')",
    "tickets": "coalesce(subject,'') || ' ' || coalesce(description,'')",
    "messages": "coalesce(body,'')",
}


def upgrade() -> None:
    for table, expr in INDEXES.items():
        op.execute(f"CREATE INDEX idx_{table}_fts ON {table} USING gin (to_tsvector('simple', {expr}))")


def downgrade() -> None:
    for table in INDEXES:
        op.execute(f"DROP INDEX IF EXISTS idx_{table}_fts")
