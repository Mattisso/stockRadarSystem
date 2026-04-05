"""Configurable entry formula scoring for buy decisions."""

from dataclasses import dataclass


@dataclass(frozen=True)
class EntryFormulaInputs:
    breakout_score: float
    liquidity_imbalance: float
    bid_stacking: float
    spread_compression: float
    volume_acceleration: float
    order_aggression: float
    spoofing_risk: float = 0.0
    ml_confidence: float | None = None


@dataclass(frozen=True)
class EntryFormulaConfig:
    breakout_score_weight: float
    liquidity_imbalance_weight: float
    bid_stacking_weight: float
    volume_acceleration_weight: float
    order_aggression_weight: float
    ml_confidence_weight: float
    entry_threshold: float
    min_spread_compression: float
    max_spoofing_risk: float
    min_ml_confidence: float = 0.0


@dataclass(frozen=True)
class EntryFormulaResult:
    score: float
    allowed: bool
    veto_reason: str | None = None


class EntryFormulaScorer:
    """Deterministic entry scorer with lightweight veto rules."""

    def __init__(self, config: EntryFormulaConfig) -> None:
        self._config = config

    def score(self, inputs: EntryFormulaInputs) -> EntryFormulaResult:
        if inputs.spread_compression < self._config.min_spread_compression:
            return EntryFormulaResult(
                score=0.0,
                allowed=False,
                veto_reason="spread_compression_too_low",
            )

        if inputs.spoofing_risk > self._config.max_spoofing_risk:
            return EntryFormulaResult(
                score=0.0,
                allowed=False,
                veto_reason="spoofing_risk_too_high",
            )

        ml_confidence = self._bounded(inputs.ml_confidence or 0.0)
        if inputs.ml_confidence is not None and ml_confidence < self._config.min_ml_confidence:
            return EntryFormulaResult(
                score=0.0,
                allowed=False,
                veto_reason="ml_confidence_too_low",
            )

        score = (
            self._config.breakout_score_weight * self._bounded(inputs.breakout_score)
            + self._config.liquidity_imbalance_weight * self._bounded(inputs.liquidity_imbalance)
            + self._config.bid_stacking_weight * self._bounded(inputs.bid_stacking)
            + self._config.volume_acceleration_weight * self._bounded(inputs.volume_acceleration)
            + self._config.order_aggression_weight * self._bounded(inputs.order_aggression)
            + self._config.ml_confidence_weight * ml_confidence
        )
        score = round(self._bounded(score), 4)
        return EntryFormulaResult(
            score=score,
            allowed=score >= self._config.entry_threshold,
            veto_reason=None,
        )

    @staticmethod
    def _bounded(value: float) -> float:
        return max(0.0, min(1.0, value))
