"""Add operational Polygon live minute aggregates table.

Revision ID: c1d2e3f4a5b6
Revises: b0c1d2e3f4a5
Create Date: 2026-04-23 09:20:00
"""

from alembic import op
import sqlalchemy as sa


revision = "c1d2e3f4a5b6"
down_revision = "b0c1d2e3f4a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "minute_aggregates_live",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("minute_ts", sa.DateTime(), nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.Integer(), nullable=False),
        sa.Column("vwap", sa.Float(), nullable=True),
        sa.Column("transactions", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("ticker", "minute_ts", name="uq_minute_aggregates_live_ticker_minute_ts"),
        schema="stock_radar",
    )
    op.create_index(
        "ix_stock_radar_minute_aggregates_live_ticker",
        "minute_aggregates_live",
        ["ticker"],
        unique=False,
        schema="stock_radar",
    )
    op.create_index(
        "ix_stock_radar_minute_aggregates_live_minute_ts",
        "minute_aggregates_live",
        ["minute_ts"],
        unique=False,
        schema="stock_radar",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_stock_radar_minute_aggregates_live_minute_ts",
        table_name="minute_aggregates_live",
        schema="stock_radar",
    )
    op.drop_index(
        "ix_stock_radar_minute_aggregates_live_ticker",
        table_name="minute_aggregates_live",
        schema="stock_radar",
    )
    op.drop_table("minute_aggregates_live", schema="stock_radar")
