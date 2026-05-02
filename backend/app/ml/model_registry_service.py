"""Persistence helpers for ML model registry metadata."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import subprocess
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.ml_model_registry import MLModelRegistry
from app.models.ml_training_example import MLTrainingExample


MODEL_NAME = "breakout_classifier"
FEATURE_SCHEMA_VERSION = 1
LABEL_DEFINITION_VERSION = 1


@dataclass(frozen=True)
class ModelRegistryRecord:
    model_version: str
    artifact_uri: str
    artifact_sha256: str | None
    training_sample_count: int
    class_balance_json: str
    metrics_json: str
    training_window_start: datetime | None
    training_window_end: datetime | None
    trained_at: datetime
    git_sha: str | None


class ModelRegistryService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def register_active_model(
        self,
        *,
        artifact_path: Path,
        sample_count: int,
        class_balance: dict,
        metrics: dict,
        trained_at: datetime | None = None,
    ) -> MLModelRegistry:
        trained_ts = trained_at or datetime.now(timezone.utc).replace(tzinfo=None)
        artifact_uri = str(artifact_path)
        artifact_sha256 = self._sha256(artifact_path)
        git_sha = self._git_sha()
        training_window_start, training_window_end = self._training_window()
        model_version = self._build_version(trained_ts, git_sha)

        self.db.query(MLModelRegistry).filter(
            MLModelRegistry.model_name == MODEL_NAME,
            MLModelRegistry.is_active.is_(True),
        ).update({"is_active": False}, synchronize_session=False)

        row = MLModelRegistry(
            model_name=MODEL_NAME,
            model_version=model_version,
            artifact_uri=artifact_uri,
            artifact_sha256=artifact_sha256,
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            label_definition_version=LABEL_DEFINITION_VERSION,
            training_sample_count=sample_count,
            class_balance_json=json.dumps(class_balance, sort_keys=True),
            metrics_json=json.dumps(metrics, sort_keys=True),
            training_window_start=training_window_start,
            training_window_end=training_window_end,
            trained_at=trained_ts,
            git_sha=git_sha,
            is_active=True,
            status="trained",
        )
        self.db.add(row)
        self.db.flush()
        return row

    def active_model(self) -> MLModelRegistry | None:
        return (
            self.db.query(MLModelRegistry)
            .filter(
                MLModelRegistry.model_name == MODEL_NAME,
                MLModelRegistry.is_active.is_(True),
            )
            .order_by(MLModelRegistry.trained_at.desc(), MLModelRegistry.id.desc())
            .first()
        )

    def _training_window(self) -> tuple[datetime | None, datetime | None]:
        row = self.db.query(
            func.min(MLTrainingExample.event_ts),
            func.max(MLTrainingExample.event_ts),
        ).one()
        return row[0], row[1]

    @staticmethod
    def _sha256(path: Path) -> str | None:
        if not path.exists():
            return None
        digest = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _git_sha() -> str | None:
        try:
            return (
                subprocess.check_output(["git", "rev-parse", "--short=12", "HEAD"], text=True)
                .strip()
            )
        except Exception:
            return None

    @staticmethod
    def _build_version(trained_at: datetime, git_sha: str | None) -> str:
        suffix = git_sha or "manual"
        return f"{trained_at.strftime('%Y%m%d%H%M%S')}-{suffix}"
