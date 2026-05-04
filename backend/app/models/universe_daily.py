from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Float, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

UNIVERSE_KIND_MARKET = "market"
UNIVERSE_KIND_OPERATIONAL = "operational"

UNIVERSE_SOURCE_POLYGON_FLATFILE = "polygon_flatfile"
UNIVERSE_SOURCE_POLYGON_GROUPED_DAY_REST = "polygon_grouped_day_rest"
UNIVERSE_SOURCE_BROKER_FILTER = "broker_filter"
UNIVERSE_SOURCE_ACTIVE_WATCHLIST = "active_watchlist"
UNIVERSE_SOURCE_LEGACY_MARKET_INFERRED = "legacy_market_inferred"
UNIVERSE_SOURCE_LEGACY_OPERATIONAL_INFERRED = "legacy_operational_inferred"


class UniverseDaily(Base):
    """Daily persisted stock universe snapshot for Secret Ingredients."""

    __tablename__ = "universe_daily"
    __table_args__ = (
        UniqueConstraint("trade_date", "ticker", "universe_kind", name="uq_universe_daily_trade_date_ticker_kind"),
        {"schema": "stock_radar"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    universe_kind: Mapped[str] = mapped_column(String(20), nullable=False, default=UNIVERSE_KIND_MARKET, index=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default=UNIVERSE_SOURCE_LEGACY_MARKET_INFERRED)
    exchange: Mapped[str] = mapped_column(String(20), nullable=False, default="NASDAQ")
    open_price: Mapped[float] = mapped_column(Float, nullable=True)
    prev_close: Mapped[float] = mapped_column(Float, nullable=True)
    last_price: Mapped[float] = mapped_column(Float, nullable=True)
    avg_volume: Mapped[int] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
