"""Add aggregate-only candidate events table.

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-04-10 23:55:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "a2b3c4d5e6f7"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "candidate_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("event_ts", sa.DateTime(), nullable=False),
        sa.Column("trigger_name", sa.String(length=64), nullable=False),
        sa.Column("trigger_payload", sa.Text(), nullable=True),
        sa.Column("last_second_ts", sa.DateTime(), nullable=True),
        sa.Column("last_minute_ts", sa.DateTime(), nullable=True),
        sa.Column("seconds_since_last_trade_bar", sa.Integer(), nullable=True),
        sa.Column("minutes_since_last_trade_bar", sa.Integer(), nullable=True),
        sa.Column("is_second_stream_stale", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_minute_stream_stale", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        schema="stock_radar",
    )
    op.create_index(
        "ix_stock_radar_candidate_events_ticker",
        "candidate_events",
        ["ticker"],
        unique=False,
        schema="stock_radar",
    )
    op.create_index(
        "ix_stock_radar_candidate_events_event_ts",
        "candidate_events",
        ["event_ts"],
        unique=False,
        schema="stock_radar",
    )
    op.create_index(
        "ix_stock_radar_candidate_events_trigger_name",
        "candidate_events",
        ["trigger_name"],
        unique=False,
        schema="stock_radar",
    )


def downgrade() -> None:
    op.drop_index("ix_stock_radar_candidate_events_trigger_name", table_name="candidate_events", schema="stock_radar")
    op.drop_index("ix_stock_radar_candidate_events_event_ts", table_name="candidate_events", schema="stock_radar")
    op.drop_index("ix_stock_radar_candidate_events_ticker", table_name="candidate_events", schema="stock_radar")
    op.drop_table("candidate_events", schema="stock_radar")
