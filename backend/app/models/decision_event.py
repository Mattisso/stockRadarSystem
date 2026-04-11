from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DecisionEvent(Base):
    """Aggregate-only decision event derived from candidate + validation state."""

    __tablename__ = "decision_events"
    __table_args__ = {"schema": "stock_radar"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    decision_ts: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    decision_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    decision_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    candidate_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    validation_pass_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seconds_since_last_trade_bar: Mapped[int | None] = mapped_column(Integer, nullable=True)
    minutes_since_last_trade_bar: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_second_stream_stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_minute_stream_stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
