"""Add operational Polygon live ticks table.

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-04-11 22:10:00
"""

from alembic import op
import sqlalchemy as sa


revision = "d5e6f7a8b9c0"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "polygon_ticks_live",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("event_type", sa.String(length=16), nullable=False),
        sa.Column("bid", sa.Float(), nullable=False),
        sa.Column("ask", sa.Float(), nullable=False),
        sa.Column("last", sa.Float(), nullable=False),
        sa.Column("volume", sa.Integer(), nullable=False),
        sa.Column("tick_ts", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        schema="stock_radar",
    )
    op.create_index(
        "ix_stock_radar_polygon_ticks_live_ticker",
        "polygon_ticks_live",
        ["ticker"],
        unique=False,
        schema="stock_radar",
    )
    op.create_index(
        "ix_stock_radar_polygon_ticks_live_event_type",
        "polygon_ticks_live",
        ["event_type"],
        unique=False,
        schema="stock_radar",
    )
    op.create_index(
        "ix_stock_radar_polygon_ticks_live_tick_ts",
        "polygon_ticks_live",
        ["tick_ts"],
        unique=False,
        schema="stock_radar",
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_stock_radar_polygon_ticks_live_ticker_tick_ts_id_desc
        ON stock_radar.polygon_ticks_live (ticker, tick_ts DESC, id DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_stock_radar_polygon_ticks_live_ticker_event_type_tick_ts_id_desc
        ON stock_radar.polygon_ticks_live (ticker, event_type, tick_ts DESC, id DESC)
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS stock_radar.ix_stock_radar_polygon_ticks_live_ticker_event_type_tick_ts_id_desc"
    )
    op.execute(
        "DROP INDEX IF EXISTS stock_radar.ix_stock_radar_polygon_ticks_live_ticker_tick_ts_id_desc"
    )
    op.drop_index(
        "ix_stock_radar_polygon_ticks_live_tick_ts",
        table_name="polygon_ticks_live",
        schema="stock_radar",
    )
    op.drop_index(
        "ix_stock_radar_polygon_ticks_live_event_type",
        table_name="polygon_ticks_live",
        schema="stock_radar",
    )
    op.drop_index(
        "ix_stock_radar_polygon_ticks_live_ticker",
        table_name="polygon_ticks_live",
        schema="stock_radar",
    )
    op.drop_table("polygon_ticks_live", schema="stock_radar")
