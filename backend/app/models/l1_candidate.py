from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class L1Candidate(Base):
    """Persisted first-pass L1 runner candidate record."""

    __tablename__ = "l1_candidates"
    __table_args__ = {"schema": "stock_radar"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    breakout_score: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=True)
    pct_change_1m: Mapped[float] = mapped_column(Float, nullable=True)
    pct_change_5m: Mapped[float] = mapped_column(Float, nullable=True)
    volume_ratio: Mapped[float] = mapped_column(Float, nullable=True)
    reason_flags: Mapped[str] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
