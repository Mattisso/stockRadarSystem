"""Add stored Polygon second aggregates table.

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-04-10 22:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e1f2a3b4c5d6"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "second_aggregates",
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
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.UniqueConstraint("ticker", "second_ts", name="uq_second_aggregates_ticker_second_ts"),
        schema="stock_radar",
    )
    context = op.get_context()
    with context.autocommit_block():
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS
            ix_stock_radar_second_aggregates_second_ts_desc
            ON stock_radar.second_aggregates (second_ts DESC)
            """
        )
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS
            ix_stock_radar_second_aggregates_ticker_second_ts_desc
            ON stock_radar.second_aggregates (ticker, second_ts DESC)
            """
        )


def downgrade() -> None:
    context = op.get_context()
    with context.autocommit_block():
        op.execute(
            """
            DROP INDEX CONCURRENTLY IF EXISTS
            stock_radar.ix_stock_radar_second_aggregates_ticker_second_ts_desc
            """
        )
        op.execute(
            """
            DROP INDEX CONCURRENTLY IF EXISTS
            stock_radar.ix_stock_radar_second_aggregates_second_ts_desc
            """
        )
    op.drop_table("second_aggregates", schema="stock_radar")
