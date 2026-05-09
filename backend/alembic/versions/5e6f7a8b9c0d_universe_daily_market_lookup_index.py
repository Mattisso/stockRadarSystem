"""Add market lookup index for universe_daily.

Revision ID: 5e6f7a8b9c0d
Revises: 4d5e6f7a8b9c
Create Date: 2026-05-09 10:30:00.000000

The hot universe_daily API paths repeatedly:

1. filter by universe_kind = 'market'
2. filter by source IN (...)
3. resolve the latest trade_date via ORDER BY trade_date DESC LIMIT 1
4. list the selected trade_date ordered by ticker ASC

The existing unique constraint on (trade_date, ticker, universe_kind) does not
cover the source predicate, so add one concurrent composite index that matches
the real filter and listing path.
"""

from alembic import op


revision = "5e6f7a8b9c0d"
down_revision = "4d5e6f7a8b9c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
            "ix_stock_radar_universe_daily_kind_source_date_ticker "
            "ON stock_radar.universe_daily "
            "(universe_kind, source, trade_date DESC, ticker ASC)"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS "
            "stock_radar.ix_stock_radar_universe_daily_kind_source_date_ticker"
        )
