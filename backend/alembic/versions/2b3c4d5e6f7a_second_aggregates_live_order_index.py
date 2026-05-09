"""Add ordering index for second_aggregates_live listing.

Revision ID: 2b3c4d5e6f7a
Revises: 1a2b3c4d5e6f
Create Date: 2026-05-08 20:45:00.000000

The /api/polygon/second-aggregates endpoint filters by a session-bounded
second_ts range and returns rows ordered by:

    ORDER BY second_ts DESC, ticker ASC

The table already has:
  - a plain second_ts index
  - a plain ticker index
  - a unique constraint on (ticker, second_ts)

Those are adequate for ticker-specific lookups, but they do not directly match
the default newest-first live listing across many universe tickers. This
concurrent index supports the route's primary listing order without blocking
writes on the hot operational table.
"""

from alembic import op


revision = "2b3c4d5e6f7a"
down_revision = "1a2b3c4d5e6f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
            "ix_stock_radar_second_aggregates_live_second_ts_ticker "
            "ON stock_radar.second_aggregates_live (second_ts DESC, ticker ASC)"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS "
            "stock_radar.ix_stock_radar_second_aggregates_live_second_ts_ticker"
        )
