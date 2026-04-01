"""Explicit Secret Sauce handoff contract and recent-event store."""

from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime

from app.engine.secret_candidate_scorer import SecretCandidateEvent


@dataclass
class SecretSauceHandoff:
    ticker: str
    score: float
    detected_at: datetime
    price_velocity_1m: float
    volume_expansion: float
    spread_pct: float
    quote_rate: float
    buy_pressure: float
    reason_flags: list[str] = field(default_factory=list)
    promotion_reason: str = "secret_candidate"
    consumer: str = "secret_sauce"
    l2_required: bool = True

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["detected_at"] = self.detected_at.isoformat()
        return payload


class SecretSauceHandoffManager:
    """Track recent Secret Sauce handoff payloads in memory."""

    def __init__(self, maxlen: int = 200) -> None:
        self._recent: deque[SecretSauceHandoff] = deque(maxlen=maxlen)

    def build(self, event: SecretCandidateEvent) -> SecretSauceHandoff:
        return SecretSauceHandoff(
            ticker=event.ticker,
            score=event.breakout_score,
            detected_at=event.timestamp,
            price_velocity_1m=event.pct_change_1m,
            volume_expansion=event.volume_ratio,
            spread_pct=event.spread_pct,
            quote_rate=event.quote_rate,
            buy_pressure=event.buy_pressure,
            reason_flags=list(event.reason_flags),
        )

    def emit(self, events: list[SecretCandidateEvent]) -> list[SecretSauceHandoff]:
        handoffs = [self.build(event) for event in events]
        for handoff in handoffs:
            self._recent.appendleft(handoff)
        return handoffs

    def recent(self, limit: int = 50) -> list[SecretSauceHandoff]:
        return list(self._recent)[:limit]
