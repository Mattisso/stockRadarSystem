"""add explicit aggregate symbol trade state

Revision ID: f7a8b9c0d1e2
Revises: d1e2f3a4b5c6
Create Date: 2026-04-29 22:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "symbol_trade_state",
        sa.Column("ticker", sa.String(length=10), primary_key=True, nullable=False),
        sa.Column("position_status", sa.String(length=16), nullable=False, server_default=sa.text("'flat'")),
        sa.Column("trade_date", sa.Date(), nullable=True),
        sa.Column("entry_decision_id", sa.Integer(), nullable=True),
        sa.Column("entry_ts", sa.DateTime(), nullable=True),
        sa.Column("entry_price", sa.Float(), nullable=True),
        sa.Column("exit_decision_id", sa.Integer(), nullable=True),
        sa.Column("exit_ts", sa.DateTime(), nullable=True),
        sa.Column("exit_price", sa.Float(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "position_status IN ('flat', 'open', 'closed')",
            name="ck_symbol_trade_state_position_status",
        ),
        schema="stock_radar",
    )
    op.create_index(
        "ix_stock_radar_symbol_trade_state_trade_date",
        "symbol_trade_state",
        ["trade_date"],
        unique=False,
        schema="stock_radar",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_stock_radar_symbol_trade_state_trade_date",
        table_name="symbol_trade_state",
        schema="stock_radar",
    )
    op.drop_table("symbol_trade_state", schema="stock_radar")
