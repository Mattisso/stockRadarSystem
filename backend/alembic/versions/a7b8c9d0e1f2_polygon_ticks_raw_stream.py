"""Add raw Polygon tick persistence table."""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "polygon_ticks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("event_type", sa.String(length=16), nullable=False),
        sa.Column("bid", sa.Float(), nullable=False),
        sa.Column("ask", sa.Float(), nullable=False),
        sa.Column("last", sa.Float(), nullable=False),
        sa.Column("volume", sa.Integer(), nullable=False),
        sa.Column("tick_ts", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        schema="stock_radar",
    )
    op.create_index(
        "ix_stock_radar_polygon_ticks_ticker",
        "polygon_ticks",
        ["ticker"],
        unique=False,
        schema="stock_radar",
    )
    op.create_index(
        "ix_stock_radar_polygon_ticks_event_type",
        "polygon_ticks",
        ["event_type"],
        unique=False,
        schema="stock_radar",
    )
    op.create_index(
        "ix_stock_radar_polygon_ticks_tick_ts",
        "polygon_ticks",
        ["tick_ts"],
        unique=False,
        schema="stock_radar",
    )


def downgrade() -> None:
    op.drop_index("ix_stock_radar_polygon_ticks_tick_ts", table_name="polygon_ticks", schema="stock_radar")
    op.drop_index("ix_stock_radar_polygon_ticks_event_type", table_name="polygon_ticks", schema="stock_radar")
    op.drop_index("ix_stock_radar_polygon_ticks_ticker", table_name="polygon_ticks", schema="stock_radar")
    op.drop_table("polygon_ticks", schema="stock_radar")
