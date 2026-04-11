from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SymbolStateLive(Base):
    """Aggregate-only live state snapshot for one symbol."""

    __tablename__ = "symbol_state_live"
    __table_args__ = {"schema": "stock_radar"}

    ticker: Mapped[str] = mapped_column(String(10), primary_key=True)
    last_second_ts: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    last_minute_ts: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    seconds_since_last_trade_bar: Mapped[int | None] = mapped_column(Integer, nullable=True)
    minutes_since_last_trade_bar: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_second_stream_stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_minute_stream_stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    rolling_second_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    rolling_second_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    rolling_second_volume: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rolling_green_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_minute_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    previous_minute_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    candidate_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    candidate_status: Mapped[str] = mapped_column(String(32), nullable=False, default="idle")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )
