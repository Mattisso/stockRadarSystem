from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MLModelRegistry(Base):
    """Versioned registry of trained ML model artifacts and metadata."""

    __tablename__ = "ml_model_registry"
    __table_args__ = {"schema": "stock_radar_ml"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    artifact_uri: Mapped[str] = mapped_column(String(512), nullable=False)
    artifact_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    feature_schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    label_definition_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    training_sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    class_balance_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    metrics_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    training_window_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    training_window_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    trained_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    git_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="trained")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
