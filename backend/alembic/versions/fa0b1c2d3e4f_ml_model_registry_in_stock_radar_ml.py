"""Add ml_model_registry table in stock_radar_ml schema.

Revision ID: fa0b1c2d3e4f
Revises: f9b0c1d2e3f4
Create Date: 2026-05-02 19:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "fa0b1c2d3e4f"
down_revision: Union[str, None] = "f9b0c1d2e3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "stock_radar_ml"


def upgrade() -> None:
    op.execute(sa.text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))

    op.create_table(
        "ml_model_registry",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("artifact_uri", sa.String(length=512), nullable=False),
        sa.Column("artifact_sha256", sa.String(length=64), nullable=True),
        sa.Column("feature_schema_version", sa.Integer(), nullable=False),
        sa.Column("label_definition_version", sa.Integer(), nullable=False),
        sa.Column("training_sample_count", sa.Integer(), nullable=False),
        sa.Column("class_balance_json", sa.Text(), nullable=True),
        sa.Column("metrics_json", sa.Text(), nullable=True),
        sa.Column("training_window_start", sa.DateTime(), nullable=True),
        sa.Column("training_window_end", sa.DateTime(), nullable=True),
        sa.Column("trained_at", sa.DateTime(), nullable=False),
        sa.Column("git_sha", sa.String(length=64), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(
        op.f(f"ix_{SCHEMA}_ml_model_registry_model_name"),
        "ml_model_registry",
        ["model_name"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        op.f(f"ix_{SCHEMA}_ml_model_registry_model_version"),
        "ml_model_registry",
        ["model_version"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        op.f(f"ix_{SCHEMA}_ml_model_registry_trained_at"),
        "ml_model_registry",
        ["trained_at"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        op.f(f"ix_{SCHEMA}_ml_model_registry_is_active"),
        "ml_model_registry",
        ["is_active"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        op.f(f"ix_{SCHEMA}_ml_model_registry_is_active"),
        table_name="ml_model_registry",
        schema=SCHEMA,
    )
    op.drop_index(
        op.f(f"ix_{SCHEMA}_ml_model_registry_trained_at"),
        table_name="ml_model_registry",
        schema=SCHEMA,
    )
    op.drop_index(
        op.f(f"ix_{SCHEMA}_ml_model_registry_model_version"),
        table_name="ml_model_registry",
        schema=SCHEMA,
    )
    op.drop_index(
        op.f(f"ix_{SCHEMA}_ml_model_registry_model_name"),
        table_name="ml_model_registry",
        schema=SCHEMA,
    )
    op.drop_table("ml_model_registry", schema=SCHEMA)
