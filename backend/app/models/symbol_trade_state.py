from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SymbolTradeState(Base):
    """Current aggregate trade lifecycle state for one symbol."""

    __tablename__ = "symbol_trade_state"
    __table_args__ = (
        CheckConstraint(
            "position_status IN ('flat', 'open', 'closed')",
            name="ck_symbol_trade_state_position_status",
        ),
        {"schema": "stock_radar"},
    )

    ticker: Mapped[str] = mapped_column(String(10), primary_key=True)
    position_status: Mapped[str] = mapped_column(String(16), nullable=False, default="flat")
    trade_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    entry_decision_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    entry_ts: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    entry_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_decision_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exit_ts: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
