"""Materialize immutable labeled training examples from operational outcomes."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.feature_snapshot import FeatureSnapshot
from app.models.ml_training_example import MLTrainingExample
from app.models.signal import Signal, SignalType
from app.models.trade import Trade, TradeStatus

FEATURE_SCHEMA_VERSION = 1
LABEL_DEFINITION_VERSION = 1


@dataclass
class MaterializationResult:
    created_count: int
    skipped_count: int


class TrainingExampleBuilder:
    """Build and persist immutable ML training rows from historical snapshots."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def materialize_pending_examples(self) -> MaterializationResult:
        snapshots = (
            self.db.query(FeatureSnapshot, Signal, Trade)
            .outerjoin(Signal, FeatureSnapshot.signal_id == Signal.id)
            .outerjoin(Trade, FeatureSnapshot.trade_id == Trade.id)
            .order_by(FeatureSnapshot.id.asc())
            .all()
        )
        existing_keys = {
            (row.feature_snapshot_id, row.label_definition_version)
            for row in self.db.query(
                MLTrainingExample.feature_snapshot_id,
                MLTrainingExample.label_definition_version,
            ).all()
        }

        created_count = 0
        skipped_count = 0
        for snapshot, signal, trade in snapshots:
            key = (snapshot.id, LABEL_DEFINITION_VERSION)
            if key in existing_keys:
                skipped_count += 1
                continue
            example = self._build_example(snapshot, signal, trade)
            if example is None:
                skipped_count += 1
                continue
            self.db.add(example)
            existing_keys.add(key)
            created_count += 1

        self.db.flush()
        return MaterializationResult(created_count=created_count, skipped_count=skipped_count)

    @staticmethod
    def _build_example(
        snapshot: FeatureSnapshot,
        signal: Signal | None,
        trade: Trade | None,
    ) -> MLTrainingExample | None:
        outcome_pnl = TrainingExampleBuilder._outcome_pnl(signal, trade)
        if outcome_pnl is None:
            return None

        label = 1 if outcome_pnl > 0 else 0
        pattern_success = (
            signal is not None
            and signal.signal_type == SignalType.BREAKOUT
            and outcome_pnl > 0
        )
        event_ts = snapshot.created_at

        return MLTrainingExample(
            feature_snapshot_id=snapshot.id,
            signal_id=snapshot.signal_id,
            trade_id=snapshot.trade_id,
            ticker=snapshot.ticker,
            event_ts=event_ts,
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            label_definition_version=LABEL_DEFINITION_VERSION,
            liquidity_imbalance=float(snapshot.liquidity_imbalance or 0.0),
            spread_compression=float(snapshot.spread_compression or 0.0),
            bid_stacking=float(snapshot.bid_stacking or 0.0),
            volume_acceleration=float(snapshot.volume_acceleration or 0.0),
            order_aggression=float(snapshot.order_aggression or 0.0),
            ml_confidence=snapshot.ml_confidence,
            composite_score=snapshot.composite_score,
            label=label,
            outcome_pnl=float(outcome_pnl),
            pattern_success=pattern_success,
            training_version=None,
        )

    @staticmethod
    def _outcome_pnl(signal: Signal | None, trade: Trade | None) -> float | None:
        if trade is not None and trade.status == TradeStatus.CLOSED and trade.pnl is not None:
            return trade.pnl
        if signal is not None and signal.outcome_pnl is not None:
            return signal.outcome_pnl
        return None
