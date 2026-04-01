"""Dedicated Secret Ingredients L1 candidate scoring."""

from dataclasses import dataclass, field
from datetime import datetime

from app.engine.l1_feature_engine import L1FeatureSnapshot


@dataclass
class SecretCandidateEvent:
    ticker: str
    breakout_score: float
    pct_change_1m: float
    pct_change_5m: float
    volume_ratio: float
    spread_pct: float
    quote_rate: float
    buy_pressure: float
    timestamp: datetime = field(default_factory=datetime.now)
    reason_flags: list[str] = field(default_factory=list)


class SecretCandidateScorer:
    """Rank L1 candidates from dedicated rolling feature snapshots."""

    def __init__(
        self,
        *,
        min_score: float,
        max_spread_pct: float,
        min_quote_rate: float,
        min_buy_pressure: float,
        min_volume_expansion: float,
    ) -> None:
        self._min_score = min_score
        self._max_spread_pct = max_spread_pct
        self._min_quote_rate = min_quote_rate
        self._min_buy_pressure = min_buy_pressure
        self._min_volume_expansion = min_volume_expansion

    def score_snapshots(self, snapshots: list[L1FeatureSnapshot]) -> list[SecretCandidateEvent]:
        events: list[SecretCandidateEvent] = []
        for snapshot in snapshots:
            event = self.score_snapshot(snapshot)
            if event is not None:
                events.append(event)
        return sorted(events, key=lambda event: event.breakout_score, reverse=True)

    def score_snapshot(self, snapshot: L1FeatureSnapshot) -> SecretCandidateEvent | None:
        if snapshot.spread_pct <= 0 or snapshot.spread_pct > self._max_spread_pct:
            return None
        if snapshot.quote_rate < self._min_quote_rate:
            return None
        if snapshot.buy_pressure < self._min_buy_pressure:
            return None
        if snapshot.volume_expansion < self._min_volume_expansion:
            return None

        price_score = self._bounded(snapshot.price_velocity_1m / 8.0)
        volume_score = self._bounded((snapshot.volume_expansion - 1.0) / 2.5)
        quote_rate_score = self._bounded(snapshot.quote_rate / 1.5)
        buy_pressure_score = self._bounded(snapshot.buy_pressure)
        spread_score = self._bounded(1.0 - (snapshot.spread_pct / self._max_spread_pct))

        score = (
            0.30 * price_score
            + 0.25 * volume_score
            + 0.20 * buy_pressure_score
            + 0.15 * spread_score
            + 0.10 * quote_rate_score
        )
        if score < self._min_score:
            return None

        reason_flags: list[str] = []
        if snapshot.price_velocity_1m >= 3.0:
            reason_flags.append("price_velocity")
        if snapshot.volume_expansion >= 1.8:
            reason_flags.append("volume_expansion")
        if snapshot.buy_pressure >= 0.65:
            reason_flags.append("buy_pressure")
        if snapshot.spread_pct <= self._max_spread_pct * 0.5:
            reason_flags.append("tight_spread")
        if snapshot.quote_rate >= max(self._min_quote_rate, 0.8):
            reason_flags.append("active_tape")

        return SecretCandidateEvent(
            ticker=snapshot.ticker,
            breakout_score=round(score, 4),
            pct_change_1m=round(snapshot.price_velocity_1m, 2),
            pct_change_5m=round(snapshot.price_velocity_1m, 2),
            volume_ratio=round(snapshot.volume_expansion, 2),
            spread_pct=round(snapshot.spread_pct, 6),
            quote_rate=round(snapshot.quote_rate, 4),
            buy_pressure=round(snapshot.buy_pressure, 4),
            timestamp=snapshot.last_updated,
            reason_flags=reason_flags,
        )

    @staticmethod
    def _bounded(value: float) -> float:
        return max(0.0, min(1.0, value))
