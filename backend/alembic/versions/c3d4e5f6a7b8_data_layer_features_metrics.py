"""Add features and performance_metrics tables for historical data layer.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-27 22:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "stock_radar"


def upgrade() -> None:
    op.create_table(
        "features",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("signal_id", sa.Integer(), nullable=True),
        sa.Column("trade_id", sa.Integer(), nullable=True),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("stage", sa.String(length=20), nullable=True),
        sa.Column("liquidity_imbalance", sa.Float(), nullable=True),
        sa.Column("spread_compression", sa.Float(), nullable=True),
        sa.Column("bid_stacking", sa.Float(), nullable=True),
        sa.Column("volume_acceleration", sa.Float(), nullable=True),
        sa.Column("order_aggression", sa.Float(), nullable=True),
        sa.Column("ml_confidence", sa.Float(), nullable=True),
        sa.Column("composite_score", sa.Float(), nullable=True),
        sa.Column("pattern_type", sa.String(length=50), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["signal_id"], [f"{SCHEMA}.signals.id"]),
        sa.ForeignKeyConstraint(["trade_id"], [f"{SCHEMA}.trades.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(op.f(f"ix_{SCHEMA}_features_ticker"), "features", ["ticker"], unique=False, schema=SCHEMA)
    op.create_index(op.f(f"ix_{SCHEMA}_features_signal_id"), "features", ["signal_id"], unique=False, schema=SCHEMA)
    op.create_index(op.f(f"ix_{SCHEMA}_features_trade_id"), "features", ["trade_id"], unique=False, schema=SCHEMA)

    op.create_table(
        "performance_metrics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("metric_name", sa.String(length=100), nullable=False),
        sa.Column("metric_scope", sa.String(length=50), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=False),
        sa.Column("metric_unit", sa.String(length=20), nullable=True),
        sa.Column("as_of", sa.DateTime(), nullable=False),
        sa.Column("window_days", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(
        op.f(f"ix_{SCHEMA}_performance_metrics_metric_name"),
        "performance_metrics",
        ["metric_name"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        op.f(f"ix_{SCHEMA}_performance_metrics_as_of"),
        "performance_metrics",
        ["as_of"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        op.f(f"ix_{SCHEMA}_performance_metrics_as_of"),
        table_name="performance_metrics",
        schema=SCHEMA,
    )
    op.drop_index(
        op.f(f"ix_{SCHEMA}_performance_metrics_metric_name"),
        table_name="performance_metrics",
        schema=SCHEMA,
    )
    op.drop_table("performance_metrics", schema=SCHEMA)

    op.drop_index(op.f(f"ix_{SCHEMA}_features_trade_id"), table_name="features", schema=SCHEMA)
    op.drop_index(op.f(f"ix_{SCHEMA}_features_signal_id"), table_name="features", schema=SCHEMA)
    op.drop_index(op.f(f"ix_{SCHEMA}_features_ticker"), table_name="features", schema=SCHEMA)
    op.drop_table("features", schema=SCHEMA)
