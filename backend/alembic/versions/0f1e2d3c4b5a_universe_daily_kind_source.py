"""Add universe kind and source to universe_daily.

This separates broad market snapshots from narrower operational snapshots
without immediately splitting the table.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0f1e2d3c4b5a"
down_revision = "fa0b1c2d3e4f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "universe_daily",
        sa.Column("universe_kind", sa.String(length=20), nullable=True, server_default=sa.text("'market'")),
        schema="stock_radar",
    )
    op.add_column(
        "universe_daily",
        sa.Column(
            "source",
            sa.String(length=50),
            nullable=True,
            server_default=sa.text("'legacy_market_inferred'"),
        ),
        schema="stock_radar",
    )
    op.execute(
        """
        UPDATE stock_radar.universe_daily
        SET
            universe_kind = CASE
                WHEN open_price IS NULL AND prev_close IS NULL AND last_price IS NULL AND avg_volume IS NULL
                    THEN 'operational'
                ELSE 'market'
            END,
            source = CASE
                WHEN open_price IS NULL AND prev_close IS NULL AND last_price IS NULL AND avg_volume IS NULL
                    THEN 'legacy_operational_inferred'
                ELSE 'legacy_market_inferred'
            END
        """
    )
    op.alter_column(
        "universe_daily",
        "universe_kind",
        nullable=False,
        server_default=None,
        schema="stock_radar",
    )
    op.alter_column(
        "universe_daily",
        "source",
        nullable=False,
        server_default=None,
        schema="stock_radar",
    )
    op.create_index(
        "ix_stock_radar_universe_daily_universe_kind",
        "universe_daily",
        ["universe_kind"],
        unique=False,
        schema="stock_radar",
    )
    op.drop_constraint(
        "uq_universe_daily_trade_date_ticker",
        "universe_daily",
        schema="stock_radar",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_universe_daily_trade_date_ticker_kind",
        "universe_daily",
        ["trade_date", "ticker", "universe_kind"],
        schema="stock_radar",
    )


def downgrade() -> None:
    # Collapse back to the older broad-market-only semantics.
    op.execute(
        """
        DELETE FROM stock_radar.universe_daily u
        WHERE u.universe_kind = 'operational'
           OR EXISTS (
                SELECT 1
                FROM stock_radar.universe_daily other
                WHERE other.trade_date = u.trade_date
                  AND other.ticker = u.ticker
                  AND other.universe_kind = 'market'
                  AND u.universe_kind <> 'market'
           )
        """
    )
    op.drop_constraint(
        "uq_universe_daily_trade_date_ticker_kind",
        "universe_daily",
        schema="stock_radar",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_universe_daily_trade_date_ticker",
        "universe_daily",
        ["trade_date", "ticker"],
        schema="stock_radar",
    )
    op.drop_index(
        "ix_stock_radar_universe_daily_universe_kind",
        table_name="universe_daily",
        schema="stock_radar",
    )
    op.drop_column("universe_daily", "source", schema="stock_radar")
    op.drop_column("universe_daily", "universe_kind", schema="stock_radar")
