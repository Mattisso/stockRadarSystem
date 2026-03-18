from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TradeStatus(str, PyEnum):
    PENDING = "pending"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    CLOSED = "closed"


class TradeSide(str, PyEnum):
    BUY = "buy"
    SELL = "sell"


class Trade(Base):
    """A trade record."""

    __tablename__ = "trades"
    __table_args__ = {"schema": "stock_radar"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    signal_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("stock_radar.signals.id"), nullable=True
    )
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    side: Mapped[TradeSide] = mapped_column(Enum(TradeSide), nullable=False)
    status: Mapped[TradeStatus] = mapped_column(
        Enum(TradeStatus), nullable=False, default=TradeStatus.PENDING
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=True)
    exit_price: Mapped[float] = mapped_column(Float, nullable=True)
    stop_loss_price: Mapped[float] = mapped_column(Float, nullable=True)
    target_price: Mapped[float] = mapped_column(Float, nullable=True)
    pnl: Mapped[float] = mapped_column(Float, nullable=True)
    signal_score: Mapped[float] = mapped_column(Float, nullable=True)
    entry_time: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    exit_time: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
