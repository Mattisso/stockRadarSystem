from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MLTrainingExample(Base):
    """Immutable labeled example materialized from feature snapshots and outcomes."""

    __tablename__ = "ml_training_examples"
    __table_args__ = (
        UniqueConstraint("feature_snapshot_id", "label_definition_version", name="uq_ml_training_example_snapshot_label"),
        {"schema": "stock_radar_ml"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    feature_snapshot_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("stock_radar.features.id"),
        nullable=False,
        index=True,
    )
    signal_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    trade_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    event_ts: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    feature_schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    label_definition_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    liquidity_imbalance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    spread_compression: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    bid_stacking: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    volume_acceleration: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    order_aggression: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ml_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    composite_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    label: Mapped[int] = mapped_column(Integer, nullable=False)
    outcome_pnl: Mapped[float] = mapped_column(Float, nullable=False)
    pattern_success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    training_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
