from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UniverseDaily(Base):
    """Daily persisted stock universe snapshot for Secret Ingredients."""

    __tablename__ = "universe_daily"
    __table_args__ = (
        UniqueConstraint("trade_date", "ticker", name="uq_universe_daily_trade_date_ticker"),
        {"schema": "stock_radar"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    exchange: Mapped[str] = mapped_column(String(20), nullable=False, default="NASDAQ")
    open_price: Mapped[float] = mapped_column(Float, nullable=True)
    prev_close: Mapped[float] = mapped_column(Float, nullable=True)
    last_price: Mapped[float] = mapped_column(Float, nullable=True)
    avg_volume: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
