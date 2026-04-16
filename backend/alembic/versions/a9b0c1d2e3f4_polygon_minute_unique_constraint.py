"""add unique constraint to polygon minute aggregates

Revision ID: a9b0c1d2e3f4
Revises: f6a7b8c9d0e1
Create Date: 2026-04-15 20:55:00.000000
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a9b0c1d2e3f4"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM stock_radar.polygon_minute_aggregates a
        USING stock_radar.polygon_minute_aggregates b
        WHERE a.ticker = b.ticker
          AND a.minute_ts = b.minute_ts
          AND a.id < b.id
        """
    )
    op.create_unique_constraint(
        "uq_polygon_minute_aggregates_ticker_minute_ts",
        "polygon_minute_aggregates",
        ["ticker", "minute_ts"],
        schema="stock_radar",
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_polygon_minute_aggregates_ticker_minute_ts",
        "polygon_minute_aggregates",
        schema="stock_radar",
        type_="unique",
    )
