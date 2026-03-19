"""Add state machine columns (stage, reason) to signals table.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-18 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None

SCHEMA = "stock_radar"


def upgrade() -> None:
    op.add_column("signals", sa.Column("stage", sa.String(20), nullable=True), schema=SCHEMA)
    op.add_column("signals", sa.Column("reason", sa.String(500), nullable=True), schema=SCHEMA)


def downgrade() -> None:
    op.drop_column("signals", "reason", schema=SCHEMA)
    op.drop_column("signals", "stage", schema=SCHEMA)
