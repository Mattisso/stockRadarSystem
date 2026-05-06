"""Add index on signals.created_at to speed up dashboard listing.

Revision ID: 1a2b3c4d5e6f
Revises: 0f1e2d3c4b5a
Create Date: 2026-05-06 02:30:00.000000

The /api/signals endpoint orders by created_at DESC LIMIT N. Without an
index this is a full sequential scan + sort, which on a 5.9M-row table
takes >8s and times out the dashboard's forkJoin (causing the
'API Health: Down' badge in the dashboard).

Built CONCURRENTLY so the migration does not lock the table; this means
the migration cannot run inside a transaction.
"""

from alembic import op


revision = "1a2b3c4d5e6f"
down_revision = "0f1e2d3c4b5a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
            "ix_stock_radar_signals_created_at "
            "ON stock_radar.signals (created_at DESC)"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS "
            "stock_radar.ix_stock_radar_signals_created_at"
        )
