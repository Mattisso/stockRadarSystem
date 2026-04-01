"""Add stop audit fields to trades."""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "trades",
        sa.Column("stop_revision_count", sa.Integer(), nullable=True),
        schema="stock_radar",
    )
    op.add_column(
        "trades",
        sa.Column("last_stop_revision_at", sa.DateTime(), nullable=True),
        schema="stock_radar",
    )
    op.add_column(
        "trades",
        sa.Column("runner_mode_started_at", sa.DateTime(), nullable=True),
        schema="stock_radar",
    )


def downgrade() -> None:
    op.drop_column("trades", "runner_mode_started_at", schema="stock_radar")
    op.drop_column("trades", "last_stop_revision_at", schema="stock_radar")
    op.drop_column("trades", "stop_revision_count", schema="stock_radar")
