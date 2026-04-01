from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class L1ToL2Event(Base):
    """Audit trail for Secret Ingredients promotions into the L2/execution side."""

    __tablename__ = "l1_to_l2_events"
    __table_args__ = {"schema": "stock_radar"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    detect_ts: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    escalate_ts: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=True)
    slot_id: Mapped[str] = mapped_column(String(32), nullable=True)
    escalation_reason: Mapped[str] = mapped_column(String(128), nullable=True)
    handoff_payload: Mapped[str] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
