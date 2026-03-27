from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class FeatureSnapshot(Base):
    """Persisted feature vector for one signal/trade decision point."""

    __tablename__ = "features"
    __table_args__ = {"schema": "stock_radar"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    signal_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("stock_radar.signals.id"), nullable=True, index=True
    )
    trade_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("stock_radar.trades.id"), nullable=True, index=True
    )
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    stage: Mapped[str | None] = mapped_column(String(20), nullable=True)
    liquidity_imbalance: Mapped[float | None] = mapped_column(Float, nullable=True)
    spread_compression: Mapped[float | None] = mapped_column(Float, nullable=True)
    bid_stacking: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_acceleration: Mapped[float | None] = mapped_column(Float, nullable=True)
    order_aggression: Mapped[float | None] = mapped_column(Float, nullable=True)
    ml_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    composite_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    pattern_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
