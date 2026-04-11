"""Add operational Polygon live second aggregates table.

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-04-11 23:05:00
"""

from alembic import op
import sqlalchemy as sa


revision = "e6f7a8b9c0d1"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "second_aggregates_live",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("second_ts", sa.DateTime(), nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.Integer(), nullable=False),
        sa.Column("vwap", sa.Float(), nullable=True),
        sa.Column("transactions", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("ticker", "second_ts", name="uq_second_aggregates_live_ticker_second_ts"),
        schema="stock_radar",
    )
    op.create_index(
        "ix_stock_radar_second_aggregates_live_ticker",
        "second_aggregates_live",
        ["ticker"],
        unique=False,
        schema="stock_radar",
    )
    op.create_index(
        "ix_stock_radar_second_aggregates_live_second_ts",
        "second_aggregates_live",
        ["second_ts"],
        unique=False,
        schema="stock_radar",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_stock_radar_second_aggregates_live_second_ts",
        table_name="second_aggregates_live",
        schema="stock_radar",
    )
    op.drop_index(
        "ix_stock_radar_second_aggregates_live_ticker",
        table_name="second_aggregates_live",
        schema="stock_radar",
    )
    op.drop_table("second_aggregates_live", schema="stock_radar")
