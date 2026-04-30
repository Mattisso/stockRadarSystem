"""add candidate event processing fields

Revision ID: f8a9b0c1d2e3
Revises: f7a8b9c0d1e2
Create Date: 2026-04-30 10:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f8a9b0c1d2e3"
down_revision: Union[str, None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "candidate_events",
        sa.Column("trigger_score", sa.Float(), nullable=True),
        schema="stock_radar",
    )
    op.add_column(
        "candidate_events",
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        schema="stock_radar",
    )
    op.create_index(
        "ix_stock_radar_candidate_events_processed_at",
        "candidate_events",
        ["processed_at"],
        unique=False,
        schema="stock_radar",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_stock_radar_candidate_events_processed_at",
        table_name="candidate_events",
        schema="stock_radar",
    )
    op.drop_column("candidate_events", "processed_at", schema="stock_radar")
    op.drop_column("candidate_events", "trigger_score", schema="stock_radar")
