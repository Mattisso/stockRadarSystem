"""Add recency/drilldown indexes for intraday Polygon pages.

Revision ID: 2b3c4d5e6f7a
Revises: 1a2b3c4d5e6f
Create Date: 2026-05-06 22:30:00.000000

These indexes accelerate the minute/second/tick pages, which primarily query by:

- trade-date time range
- optional ticker / event type
- descending recency order
- pagination

Built CONCURRENTLY so the migration does not take intrusive locks on the hot
intraday tables; this means the migration cannot run inside a transaction.
"""

from alembic import op


revision = "2b3c4d5e6f7a"
down_revision = "1a2b3c4d5e6f"
branch_labels = None
depends_on = None


INDEX_STATEMENTS = (
    (
        "ix_stock_radar_minute_aggregates_live_minute_ts_id_desc",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        "ix_stock_radar_minute_aggregates_live_minute_ts_id_desc "
        "ON stock_radar.minute_aggregates_live (minute_ts DESC, id DESC)",
    ),
    (
        "ix_stock_radar_minute_aggregates_live_ticker_minute_ts_id_desc",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        "ix_stock_radar_minute_aggregates_live_ticker_minute_ts_id_desc "
        "ON stock_radar.minute_aggregates_live (ticker, minute_ts DESC, id DESC)",
    ),
    (
        "ix_stock_radar_polygon_minute_aggregates_minute_ts_id_desc",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        "ix_stock_radar_polygon_minute_aggregates_minute_ts_id_desc "
        "ON stock_radar.polygon_minute_aggregates (minute_ts DESC, id DESC)",
    ),
    (
        "ix_stock_radar_polygon_minute_aggregates_ticker_minute_ts_id_desc",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        "ix_stock_radar_polygon_minute_aggregates_ticker_minute_ts_id_desc "
        "ON stock_radar.polygon_minute_aggregates (ticker, minute_ts DESC, id DESC)",
    ),
    (
        "ix_stock_radar_second_aggregates_live_second_ts_id_desc",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        "ix_stock_radar_second_aggregates_live_second_ts_id_desc "
        "ON stock_radar.second_aggregates_live (second_ts DESC, id DESC)",
    ),
    (
        "ix_stock_radar_second_aggregates_live_ticker_second_ts_id_desc",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        "ix_stock_radar_second_aggregates_live_ticker_second_ts_id_desc "
        "ON stock_radar.second_aggregates_live (ticker, second_ts DESC, id DESC)",
    ),
    (
        "ix_stock_radar_second_aggregates_second_ts_id_desc",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        "ix_stock_radar_second_aggregates_second_ts_id_desc "
        "ON stock_radar.second_aggregates (second_ts DESC, id DESC)",
    ),
    (
        "ix_stock_radar_second_aggregates_ticker_second_ts_id_desc",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        "ix_stock_radar_second_aggregates_ticker_second_ts_id_desc "
        "ON stock_radar.second_aggregates (ticker, second_ts DESC, id DESC)",
    ),
    (
        "ix_stock_radar_polygon_ticks_live_tick_ts_id_desc",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        "ix_stock_radar_polygon_ticks_live_tick_ts_id_desc "
        "ON stock_radar.polygon_ticks_live (tick_ts DESC, id DESC)",
    ),
    (
        "ix_stock_radar_polygon_ticks_live_ticker_tick_ts_id_desc",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        "ix_stock_radar_polygon_ticks_live_ticker_tick_ts_id_desc "
        "ON stock_radar.polygon_ticks_live (ticker, tick_ts DESC, id DESC)",
    ),
    (
        "ix_stock_radar_polygon_ticks_live_ticker_event_type_tick_ts_id_desc",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        "ix_stock_radar_polygon_ticks_live_ticker_event_type_tick_ts_id_desc "
        "ON stock_radar.polygon_ticks_live (ticker, event_type, tick_ts DESC, id DESC)",
    ),
    (
        "ix_stock_radar_polygon_ticks_tick_ts_id_desc",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        "ix_stock_radar_polygon_ticks_tick_ts_id_desc "
        "ON stock_radar.polygon_ticks (tick_ts DESC, id DESC)",
    ),
    (
        "ix_stock_radar_polygon_ticks_ticker_tick_ts_id_desc",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        "ix_stock_radar_polygon_ticks_ticker_tick_ts_id_desc "
        "ON stock_radar.polygon_ticks (ticker, tick_ts DESC, id DESC)",
    ),
    (
        "ix_stock_radar_polygon_ticks_ticker_event_type_tick_ts_id_desc",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        "ix_stock_radar_polygon_ticks_ticker_event_type_tick_ts_id_desc "
        "ON stock_radar.polygon_ticks (ticker, event_type, tick_ts DESC, id DESC)",
    ),
)


def upgrade() -> None:
    with op.get_context().autocommit_block():
        for _name, statement in INDEX_STATEMENTS:
            op.execute(statement)


def downgrade() -> None:
    with op.get_context().autocommit_block():
        for name, _statement in reversed(INDEX_STATEMENTS):
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS stock_radar.{name}")
