"""Add ml_training_examples table in stock_radar_ml schema.

Revision ID: f9b0c1d2e3f4
Revises: f8a9b0c1d2e3
Create Date: 2026-05-02 18:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f9b0c1d2e3f4"
down_revision: Union[str, None] = "f8a9b0c1d2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "stock_radar_ml"
CORE_SCHEMA = "stock_radar"


def upgrade() -> None:
    op.execute(sa.text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))

    op.create_table(
        "ml_training_examples",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("feature_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("signal_id", sa.Integer(), nullable=True),
        sa.Column("trade_id", sa.Integer(), nullable=True),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("event_ts", sa.DateTime(), nullable=False),
        sa.Column("feature_schema_version", sa.Integer(), nullable=False),
        sa.Column("label_definition_version", sa.Integer(), nullable=False),
        sa.Column("liquidity_imbalance", sa.Float(), nullable=False),
        sa.Column("spread_compression", sa.Float(), nullable=False),
        sa.Column("bid_stacking", sa.Float(), nullable=False),
        sa.Column("volume_acceleration", sa.Float(), nullable=False),
        sa.Column("order_aggression", sa.Float(), nullable=False),
        sa.Column("ml_confidence", sa.Float(), nullable=True),
        sa.Column("composite_score", sa.Float(), nullable=True),
        sa.Column("label", sa.Integer(), nullable=False),
        sa.Column("outcome_pnl", sa.Float(), nullable=False),
        sa.Column("pattern_success", sa.Boolean(), nullable=False),
        sa.Column("training_version", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["feature_snapshot_id"], [f"{CORE_SCHEMA}.features.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "feature_snapshot_id",
            "label_definition_version",
            name="uq_ml_training_example_snapshot_label",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        op.f(f"ix_{SCHEMA}_ml_training_examples_feature_snapshot_id"),
        "ml_training_examples",
        ["feature_snapshot_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        op.f(f"ix_{SCHEMA}_ml_training_examples_signal_id"),
        "ml_training_examples",
        ["signal_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        op.f(f"ix_{SCHEMA}_ml_training_examples_trade_id"),
        "ml_training_examples",
        ["trade_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        op.f(f"ix_{SCHEMA}_ml_training_examples_ticker"),
        "ml_training_examples",
        ["ticker"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        op.f(f"ix_{SCHEMA}_ml_training_examples_event_ts"),
        "ml_training_examples",
        ["event_ts"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        op.f(f"ix_{SCHEMA}_ml_training_examples_event_ts"),
        table_name="ml_training_examples",
        schema=SCHEMA,
    )
    op.drop_index(
        op.f(f"ix_{SCHEMA}_ml_training_examples_ticker"),
        table_name="ml_training_examples",
        schema=SCHEMA,
    )
    op.drop_index(
        op.f(f"ix_{SCHEMA}_ml_training_examples_trade_id"),
        table_name="ml_training_examples",
        schema=SCHEMA,
    )
    op.drop_index(
        op.f(f"ix_{SCHEMA}_ml_training_examples_signal_id"),
        table_name="ml_training_examples",
        schema=SCHEMA,
    )
    op.drop_index(
        op.f(f"ix_{SCHEMA}_ml_training_examples_feature_snapshot_id"),
        table_name="ml_training_examples",
        schema=SCHEMA,
    )
    op.drop_table("ml_training_examples", schema=SCHEMA)
