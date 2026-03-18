"""Sprint 9: add signal_id FK on trades, ml_confidence on signals.

Revision ID: a1b2c3d4e5f6
Revises: eccb39e7875c
Create Date: 2026-03-17 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "eccb39e7875c"
branch_labels = None
depends_on = None

SCHEMA = "stock_radar"


def upgrade() -> None:
    op.add_column("signals", sa.Column("ml_confidence", sa.Float(), nullable=True), schema=SCHEMA)
    op.add_column("trades", sa.Column("signal_id", sa.Integer(), nullable=True), schema=SCHEMA)
    op.create_foreign_key(
        "fk_trades_signal_id",
        "trades",
        "signals",
        ["signal_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_constraint("fk_trades_signal_id", "trades", schema=SCHEMA, type_="foreignkey")
    op.drop_column("trades", "signal_id", schema=SCHEMA)
    op.drop_column("signals", "ml_confidence", schema=SCHEMA)
