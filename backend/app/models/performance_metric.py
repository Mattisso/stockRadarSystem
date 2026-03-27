from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PerformanceMetric(Base):
    """Historical aggregated performance metrics for analytics and learning."""

    __tablename__ = "performance_metrics"
    __table_args__ = {"schema": "stock_radar"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    metric_scope: Mapped[str] = mapped_column(String(50), nullable=False, default="system")
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    metric_unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    as_of: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    window_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
