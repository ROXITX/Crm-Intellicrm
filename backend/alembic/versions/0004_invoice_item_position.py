"""invoice item position (stable line ordering)

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("invoice_items", sa.Column("position", sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    op.drop_column("invoice_items", "position")
