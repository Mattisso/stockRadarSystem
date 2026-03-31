"""add trade execution metadata columns

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-30 20:45:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("trades", sa.Column("entry_order_id", sa.String(length=64), nullable=True), schema="stock_radar")
    op.add_column("trades", sa.Column("target_order_id", sa.String(length=64), nullable=True), schema="stock_radar")
    op.add_column("trades", sa.Column("stop_order_id", sa.String(length=64), nullable=True), schema="stock_radar")
    op.add_column("trades", sa.Column("last_stop_price", sa.Float(), nullable=True), schema="stock_radar")
    op.add_column("trades", sa.Column("runner_mode", sa.String(length=8), nullable=True), schema="stock_radar")
    op.add_column("trades", sa.Column("execution_phase", sa.String(length=32), nullable=True), schema="stock_radar")
    op.add_column("trades", sa.Column("close_reason", sa.String(length=64), nullable=True), schema="stock_radar")


def downgrade() -> None:
    op.drop_column("trades", "close_reason", schema="stock_radar")
    op.drop_column("trades", "execution_phase", schema="stock_radar")
    op.drop_column("trades", "runner_mode", schema="stock_radar")
    op.drop_column("trades", "last_stop_price", schema="stock_radar")
    op.drop_column("trades", "stop_order_id", schema="stock_radar")
    op.drop_column("trades", "target_order_id", schema="stock_radar")
    op.drop_column("trades", "entry_order_id", schema="stock_radar")
