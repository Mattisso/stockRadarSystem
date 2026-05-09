"""Add ordering index for minute_aggregates_live listing.

Revision ID: 3c4d5e6f7a8b
Revises: 2b3c4d5e6f7a
Create Date: 2026-05-08 21:00:00.000000

The /api/polygon/minute-aggregates endpoint filters by a session-bounded
minute_ts range and returns rows ordered by:

    ORDER BY minute_ts DESC, id DESC

The table already has:
  - a plain minute_ts index
  - a plain ticker index
  - a unique constraint on (ticker, minute_ts)

Those are adequate for ticker-specific lookups, but they do not directly match
the default newest-first live listing. This concurrent index supports the
route's primary listing order without blocking writes on the hot operational
table.
"""

from alembic import op


revision = "3c4d5e6f7a8b"
down_revision = "2b3c4d5e6f7a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
            "ix_stock_radar_minute_aggregates_live_minute_ts_id_desc "
            "ON stock_radar.minute_aggregates_live (minute_ts DESC, id DESC)"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS "
            "stock_radar.ix_stock_radar_minute_aggregates_live_minute_ts_id_desc"
        )
