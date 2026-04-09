"""Add composite indexes for Polygon tick query patterns.

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-04-08 23:45:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    context = op.get_context()
    with context.autocommit_block():
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS
            ix_stock_radar_polygon_ticks_ticker_tick_ts_id_desc
            ON stock_radar.polygon_ticks (ticker, tick_ts DESC, id DESC)
            """
        )
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS
            ix_stock_radar_polygon_ticks_ticker_event_type_tick_ts_id_desc
            ON stock_radar.polygon_ticks (ticker, event_type, tick_ts DESC, id DESC)
            """
        )


def downgrade() -> None:
    context = op.get_context()
    with context.autocommit_block():
        op.execute(
            """
            DROP INDEX CONCURRENTLY IF EXISTS
            stock_radar.ix_stock_radar_polygon_ticks_ticker_event_type_tick_ts_id_desc
            """
        )
        op.execute(
            """
            DROP INDEX CONCURRENTLY IF EXISTS
            stock_radar.ix_stock_radar_polygon_ticks_ticker_tick_ts_id_desc
            """
        )
