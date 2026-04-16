"""tighten symbol state live constraints

Revision ID: b0c1d2e3f4a5
Revises: a9b0c1d2e3f4
Create Date: 2026-04-15 21:15:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b0c1d2e3f4a5"
down_revision: Union[str, None] = "a9b0c1d2e3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE stock_radar.symbol_state_live
        SET updated_at = now()
        WHERE updated_at IS NULL
        """
    )
    op.execute(
        """
        UPDATE stock_radar.symbol_state_live
        SET seconds_since_last_trade_bar = 0
        WHERE seconds_since_last_trade_bar < 0
        """
    )
    op.execute(
        """
        UPDATE stock_radar.symbol_state_live
        SET minutes_since_last_trade_bar = 0
        WHERE minutes_since_last_trade_bar < 0
        """
    )
    op.execute(
        """
        UPDATE stock_radar.symbol_state_live
        SET rolling_second_volume = 0
        WHERE rolling_second_volume < 0
        """
    )
    op.execute(
        """
        UPDATE stock_radar.symbol_state_live
        SET rolling_green_count = 0
        WHERE rolling_green_count < 0
        """
    )
    op.execute(
        """
        UPDATE stock_radar.symbol_state_live
        SET validation_pass_count = 0
        WHERE validation_pass_count < 0
        """
    )
    op.alter_column(
        "symbol_state_live",
        "updated_at",
        existing_type=sa.DateTime(),
        nullable=False,
        schema="stock_radar",
    )
    op.create_check_constraint(
        "ck_symbol_state_live_seconds_since_non_negative",
        "symbol_state_live",
        "seconds_since_last_trade_bar IS NULL OR seconds_since_last_trade_bar >= 0",
        schema="stock_radar",
    )
    op.create_check_constraint(
        "ck_symbol_state_live_minutes_since_non_negative",
        "symbol_state_live",
        "minutes_since_last_trade_bar IS NULL OR minutes_since_last_trade_bar >= 0",
        schema="stock_radar",
    )
    op.create_check_constraint(
        "ck_symbol_state_live_rolling_second_volume_non_negative",
        "symbol_state_live",
        "rolling_second_volume >= 0",
        schema="stock_radar",
    )
    op.create_check_constraint(
        "ck_symbol_state_live_rolling_green_count_non_negative",
        "symbol_state_live",
        "rolling_green_count >= 0",
        schema="stock_radar",
    )
    op.create_check_constraint(
        "ck_symbol_state_live_validation_pass_count_non_negative",
        "symbol_state_live",
        "validation_pass_count >= 0",
        schema="stock_radar",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_symbol_state_live_validation_pass_count_non_negative",
        "symbol_state_live",
        schema="stock_radar",
        type_="check",
    )
    op.drop_constraint(
        "ck_symbol_state_live_rolling_green_count_non_negative",
        "symbol_state_live",
        schema="stock_radar",
        type_="check",
    )
    op.drop_constraint(
        "ck_symbol_state_live_rolling_second_volume_non_negative",
        "symbol_state_live",
        schema="stock_radar",
        type_="check",
    )
    op.drop_constraint(
        "ck_symbol_state_live_minutes_since_non_negative",
        "symbol_state_live",
        schema="stock_radar",
        type_="check",
    )
    op.drop_constraint(
        "ck_symbol_state_live_seconds_since_non_negative",
        "symbol_state_live",
        schema="stock_radar",
        type_="check",
    )
    op.alter_column(
        "symbol_state_live",
        "updated_at",
        existing_type=sa.DateTime(),
        nullable=True,
        schema="stock_radar",
    )
