"""Add ordering index for polygon_day_aggregates listing.

Revision ID: 4d5e6f7a8b9c
Revises: 3c4d5e6f7a8b
Create Date: 2026-05-08 22:10:00.000000

The /api/polygon/day-aggregates endpoint:

1. resolves the latest trade date via ORDER BY trade_date DESC LIMIT 1
2. filters rows by trade_date
3. returns rows ordered by trade_date DESC, ticker ASC

The table already has single-column indexes on trade_date and ticker, but the
listing path benefits from a composite index that matches the endpoint's common
filter and sort pattern.
"""

from alembic import op


revision = "4d5e6f7a8b9c"
down_revision = "3c4d5e6f7a8b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
            "ix_stock_radar_polygon_day_aggregates_trade_date_ticker "
            "ON stock_radar.polygon_day_aggregates (trade_date DESC, ticker ASC)"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS "
            "stock_radar.ix_stock_radar_polygon_day_aggregates_trade_date_ticker"
        )
