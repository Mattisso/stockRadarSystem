"""Add Secret Ingredients first-sprint tables."""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "universe_daily",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("exchange", sa.String(length=20), nullable=False),
        sa.Column("open_price", sa.Float(), nullable=True),
        sa.Column("prev_close", sa.Float(), nullable=True),
        sa.Column("last_price", sa.Float(), nullable=True),
        sa.Column("avg_volume", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("trade_date", "ticker", name="uq_universe_daily_trade_date_ticker"),
        schema="stock_radar",
    )
    op.create_index(
        "ix_stock_radar_universe_daily_trade_date",
        "universe_daily",
        ["trade_date"],
        unique=False,
        schema="stock_radar",
    )
    op.create_index(
        "ix_stock_radar_universe_daily_ticker",
        "universe_daily",
        ["ticker"],
        unique=False,
        schema="stock_radar",
    )

    op.create_table(
        "l1_candidates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("detected_at", sa.DateTime(), nullable=False),
        sa.Column("breakout_score", sa.Float(), nullable=False),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("pct_change_1m", sa.Float(), nullable=True),
        sa.Column("pct_change_5m", sa.Float(), nullable=True),
        sa.Column("volume_ratio", sa.Float(), nullable=True),
        sa.Column("reason_flags", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        schema="stock_radar",
    )
    op.create_index(
        "ix_stock_radar_l1_candidates_ticker",
        "l1_candidates",
        ["ticker"],
        unique=False,
        schema="stock_radar",
    )
    op.create_index(
        "ix_stock_radar_l1_candidates_detected_at",
        "l1_candidates",
        ["detected_at"],
        unique=False,
        schema="stock_radar",
    )

    op.create_table(
        "l1_to_l2_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("detect_ts", sa.DateTime(), nullable=False),
        sa.Column("escalate_ts", sa.DateTime(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("slot_id", sa.String(length=32), nullable=True),
        sa.Column("escalation_reason", sa.String(length=128), nullable=True),
        sa.Column("handoff_payload", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        schema="stock_radar",
    )
    op.create_index(
        "ix_stock_radar_l1_to_l2_events_ticker",
        "l1_to_l2_events",
        ["ticker"],
        unique=False,
        schema="stock_radar",
    )
    op.create_index(
        "ix_stock_radar_l1_to_l2_events_detect_ts",
        "l1_to_l2_events",
        ["detect_ts"],
        unique=False,
        schema="stock_radar",
    )


def downgrade() -> None:
    op.drop_index("ix_stock_radar_l1_to_l2_events_detect_ts", table_name="l1_to_l2_events", schema="stock_radar")
    op.drop_index("ix_stock_radar_l1_to_l2_events_ticker", table_name="l1_to_l2_events", schema="stock_radar")
    op.drop_table("l1_to_l2_events", schema="stock_radar")

    op.drop_index("ix_stock_radar_l1_candidates_detected_at", table_name="l1_candidates", schema="stock_radar")
    op.drop_index("ix_stock_radar_l1_candidates_ticker", table_name="l1_candidates", schema="stock_radar")
    op.drop_table("l1_candidates", schema="stock_radar")

    op.drop_index("ix_stock_radar_universe_daily_ticker", table_name="universe_daily", schema="stock_radar")
    op.drop_index("ix_stock_radar_universe_daily_trade_date", table_name="universe_daily", schema="stock_radar")
    op.drop_table("universe_daily", schema="stock_radar")
