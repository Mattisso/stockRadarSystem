"""Add aggregate-only decision events table.

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-04-11 00:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "c4d5e6f7a8b9"
down_revision = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "decision_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("decision_ts", sa.DateTime(), nullable=False),
        sa.Column("decision_type", sa.String(length=32), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=False),
        sa.Column("decision_payload", sa.Text(), nullable=True),
        sa.Column("candidate_score", sa.Float(), nullable=True),
        sa.Column("validation_pass_count", sa.Integer(), nullable=True),
        sa.Column("seconds_since_last_trade_bar", sa.Integer(), nullable=True),
        sa.Column("minutes_since_last_trade_bar", sa.Integer(), nullable=True),
        sa.Column("is_second_stream_stale", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_minute_stream_stale", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        schema="stock_radar",
    )
    op.create_index("ix_stock_radar_decision_events_ticker", "decision_events", ["ticker"], unique=False, schema="stock_radar")
    op.create_index("ix_stock_radar_decision_events_decision_ts", "decision_events", ["decision_ts"], unique=False, schema="stock_radar")
    op.create_index("ix_stock_radar_decision_events_decision_type", "decision_events", ["decision_type"], unique=False, schema="stock_radar")


def downgrade() -> None:
    op.drop_index("ix_stock_radar_decision_events_decision_type", table_name="decision_events", schema="stock_radar")
    op.drop_index("ix_stock_radar_decision_events_decision_ts", table_name="decision_events", schema="stock_radar")
    op.drop_index("ix_stock_radar_decision_events_ticker", table_name="decision_events", schema="stock_radar")
    op.drop_table("decision_events", schema="stock_radar")
