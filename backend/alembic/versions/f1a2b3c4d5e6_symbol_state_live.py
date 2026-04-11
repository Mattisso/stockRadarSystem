"""Add live aggregate state table.

Revision ID: f1a2b3c4d5e6
Revises: e1f2a3b4c5d6
Create Date: 2026-04-10 23:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "f1a2b3c4d5e6"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "symbol_state_live",
        sa.Column("ticker", sa.String(length=10), primary_key=True),
        sa.Column("last_second_ts", sa.DateTime(), nullable=True),
        sa.Column("last_minute_ts", sa.DateTime(), nullable=True),
        sa.Column("seconds_since_last_trade_bar", sa.Integer(), nullable=True),
        sa.Column("minutes_since_last_trade_bar", sa.Integer(), nullable=True),
        sa.Column("is_second_stream_stale", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_minute_stream_stale", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("rolling_second_high", sa.Float(), nullable=True),
        sa.Column("rolling_second_low", sa.Float(), nullable=True),
        sa.Column("rolling_second_volume", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("rolling_green_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("current_minute_high", sa.Float(), nullable=True),
        sa.Column("previous_minute_high", sa.Float(), nullable=True),
        sa.Column("candidate_score", sa.Float(), nullable=True),
        sa.Column("candidate_status", sa.String(length=32), nullable=False, server_default=sa.text("'idle'")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        schema="stock_radar",
    )
    op.create_index(
        "ix_stock_radar_symbol_state_live_last_second_ts",
        "symbol_state_live",
        ["last_second_ts"],
        unique=False,
        schema="stock_radar",
    )
    op.create_index(
        "ix_stock_radar_symbol_state_live_last_minute_ts",
        "symbol_state_live",
        ["last_minute_ts"],
        unique=False,
        schema="stock_radar",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_stock_radar_symbol_state_live_last_minute_ts",
        table_name="symbol_state_live",
        schema="stock_radar",
    )
    op.drop_index(
        "ix_stock_radar_symbol_state_live_last_second_ts",
        table_name="symbol_state_live",
        schema="stock_radar",
    )
    op.drop_table("symbol_state_live", schema="stock_radar")
