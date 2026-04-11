from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CandidateEvent(Base):
    """Aggregate-only trigger event emitted from second-bar evaluation."""

    __tablename__ = "candidate_events"
    __table_args__ = {"schema": "stock_radar"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    event_ts: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    trigger_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    trigger_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_second_ts: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_minute_ts: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    seconds_since_last_trade_bar: Mapped[int | None] = mapped_column(Integer, nullable=True)
    minutes_since_last_trade_bar: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_second_stream_stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_minute_stream_stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
