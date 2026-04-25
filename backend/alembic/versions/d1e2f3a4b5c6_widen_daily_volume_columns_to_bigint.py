"""Widen daily volume/count columns to bigint.

Revision ID: d1e2f3a4b5c6
Revises: c1d2e3f4a5b6
Create Date: 2026-04-25 14:45:00
"""

from alembic import op
import sqlalchemy as sa


revision = "d1e2f3a4b5c6"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "polygon_day_aggregates",
        "volume",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
        schema="stock_radar",
    )
    op.alter_column(
        "polygon_day_aggregates",
        "transactions",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True,
        schema="stock_radar",
    )
    op.alter_column(
        "universe_daily",
        "avg_volume",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True,
        schema="stock_radar",
    )
    op.alter_column(
        "symbols",
        "avg_volume",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True,
        schema="stock_radar",
    )


def downgrade() -> None:
    op.alter_column(
        "symbols",
        "avg_volume",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=True,
        schema="stock_radar",
    )
    op.alter_column(
        "universe_daily",
        "avg_volume",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=True,
        schema="stock_radar",
    )
    op.alter_column(
        "polygon_day_aggregates",
        "transactions",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=True,
        schema="stock_radar",
    )
    op.alter_column(
        "polygon_day_aggregates",
        "volume",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False,
        schema="stock_radar",
    )
