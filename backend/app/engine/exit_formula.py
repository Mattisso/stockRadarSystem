"""Configurable exit formula scoring for sell decisions."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExitFormulaInputs:
    l2_weakness: float
    momentum_decay: float
    spread_worsening: float
    pnl_drawdown_from_peak: float


@dataclass(frozen=True)
class ExitFormulaConfig:
    l2_weakness_weight: float
    momentum_decay_weight: float
    spread_worsening_weight: float
    pnl_drawdown_from_peak_weight: float
    exit_threshold: float


@dataclass(frozen=True)
class ExitFormulaResult:
    score: float
    should_exit: bool


class ExitFormulaScorer:
    """Deterministic exit scorer using bounded normalized inputs."""

    def __init__(self, config: ExitFormulaConfig) -> None:
        self._config = config

    def score(self, inputs: ExitFormulaInputs) -> ExitFormulaResult:
        score = (
            self._config.l2_weakness_weight * self._bounded(inputs.l2_weakness)
            + self._config.momentum_decay_weight * self._bounded(inputs.momentum_decay)
            + self._config.spread_worsening_weight * self._bounded(inputs.spread_worsening)
            + self._config.pnl_drawdown_from_peak_weight * self._bounded(inputs.pnl_drawdown_from_peak)
        )
        score = round(self._bounded(score), 4)
        return ExitFormulaResult(score=score, should_exit=score >= self._config.exit_threshold)

    @staticmethod
    def _bounded(value: float) -> float:
        return max(0.0, min(1.0, value))
