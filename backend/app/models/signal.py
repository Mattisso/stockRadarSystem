from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Boolean, DateTime, Enum, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SignalType(str, PyEnum):
    BREAKOUT = "breakout"
    FALSE_BREAKOUT = "false_breakout"


class Signal(Base):
    """A breakout signal record."""

    __tablename__ = "signals"
    __table_args__ = {"schema": "stock_radar"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    signal_type: Mapped[SignalType] = mapped_column(Enum(SignalType), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    liquidity_imbalance: Mapped[float] = mapped_column(Float, nullable=True)
    spread_compression: Mapped[float] = mapped_column(Float, nullable=True)
    bid_stacking: Mapped[float] = mapped_column(Float, nullable=True)
    volume_acceleration: Mapped[float] = mapped_column(Float, nullable=True)
    order_aggression: Mapped[float] = mapped_column(Float, nullable=True)
    acted_on: Mapped[bool] = mapped_column(Boolean, default=False)
    outcome_pnl: Mapped[float] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
