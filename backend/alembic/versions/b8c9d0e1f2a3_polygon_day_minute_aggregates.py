"""Add Polygon day and minute aggregate tables."""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "polygon_day_aggregates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.Integer(), nullable=False),
        sa.Column("vwap", sa.Float(), nullable=True),
        sa.Column("transactions", sa.Integer(), nullable=True),
        sa.Column("source_ts", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        schema="stock_radar",
    )
    op.create_index(
        "ix_stock_radar_polygon_day_aggregates_trade_date",
        "polygon_day_aggregates",
        ["trade_date"],
        unique=False,
        schema="stock_radar",
    )
    op.create_index(
        "ix_stock_radar_polygon_day_aggregates_ticker",
        "polygon_day_aggregates",
        ["ticker"],
        unique=False,
        schema="stock_radar",
    )

    op.create_table(
        "polygon_minute_aggregates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("minute_ts", sa.DateTime(), nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.Integer(), nullable=False),
        sa.Column("vwap", sa.Float(), nullable=True),
        sa.Column("transactions", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        schema="stock_radar",
    )
    op.create_index(
        "ix_stock_radar_polygon_minute_aggregates_ticker",
        "polygon_minute_aggregates",
        ["ticker"],
        unique=False,
        schema="stock_radar",
    )
    op.create_index(
        "ix_stock_radar_polygon_minute_aggregates_minute_ts",
        "polygon_minute_aggregates",
        ["minute_ts"],
        unique=False,
        schema="stock_radar",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_stock_radar_polygon_minute_aggregates_minute_ts",
        table_name="polygon_minute_aggregates",
        schema="stock_radar",
    )
    op.drop_index(
        "ix_stock_radar_polygon_minute_aggregates_ticker",
        table_name="polygon_minute_aggregates",
        schema="stock_radar",
    )
    op.drop_table("polygon_minute_aggregates", schema="stock_radar")

    op.drop_index(
        "ix_stock_radar_polygon_day_aggregates_ticker",
        table_name="polygon_day_aggregates",
        schema="stock_radar",
    )
    op.drop_index(
        "ix_stock_radar_polygon_day_aggregates_trade_date",
        table_name="polygon_day_aggregates",
        schema="stock_radar",
    )
    op.drop_table("polygon_day_aggregates", schema="stock_radar")
