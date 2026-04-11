"""Add validation fields to symbol_state_live.

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-04-10 23:45:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "b3c4d5e6f7a8"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "symbol_state_live",
        sa.Column("validation_score", sa.Float(), nullable=True),
        schema="stock_radar",
    )
    op.add_column(
        "symbol_state_live",
        sa.Column("validation_pass_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        schema="stock_radar",
    )


def downgrade() -> None:
    op.drop_column("symbol_state_live", "validation_pass_count", schema="stock_radar")
    op.drop_column("symbol_state_live", "validation_score", schema="stock_radar")
