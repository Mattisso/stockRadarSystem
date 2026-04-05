"""Add formula output persistence columns.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-04-05 18:05:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "signals",
        sa.Column("entry_formula_score", sa.Float(), nullable=True),
        schema="stock_radar",
    )
    op.add_column(
        "signals",
        sa.Column("entry_formula_preset", sa.String(length=32), nullable=True),
        schema="stock_radar",
    )
    op.add_column(
        "trades",
        sa.Column("entry_formula_preset", sa.String(length=32), nullable=True),
        schema="stock_radar",
    )
    op.add_column(
        "trades",
        sa.Column("exit_formula_score", sa.Float(), nullable=True),
        schema="stock_radar",
    )
    op.add_column(
        "trades",
        sa.Column("exit_formula_preset", sa.String(length=32), nullable=True),
        schema="stock_radar",
    )


def downgrade() -> None:
    op.drop_column("trades", "exit_formula_preset", schema="stock_radar")
    op.drop_column("trades", "exit_formula_score", schema="stock_radar")
    op.drop_column("trades", "entry_formula_preset", schema="stock_radar")
    op.drop_column("signals", "entry_formula_preset", schema="stock_radar")
    op.drop_column("signals", "entry_formula_score", schema="stock_radar")
