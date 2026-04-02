"""Replay-style integration validator for the Secret Ingredients runtime."""

from dataclasses import dataclass
from datetime import datetime

from app.broker.interface import Quote
from app.engine.l1_feature_engine import L1FeatureEngine
from app.engine.l2_promotion_queue import L2PromotionQueue
from app.engine.secret_candidate_scorer import SecretCandidateScorer
from app.engine.secret_sauce_handoff import SecretSauceHandoffManager


class _ReplayL2Manager:
    def __init__(self) -> None:
        self.active_symbols: set[str] = set()

    async def subscribe(self, ticker: str) -> bool:
        if ticker in self.active_symbols:
            return False
        self.active_symbols.add(ticker)
        return True

    async def unsubscribe(self, ticker: str) -> bool:
        existed = ticker in self.active_symbols
        self.active_symbols.discard(ticker)
        return existed


@dataclass
class SecretReplayValidationResult:
    snapshots: list[dict]
    candidates: list[dict]
    handoffs: list[dict]
    queue: dict
    promoted_tickers: list[str]


class SecretReplayValidator:
    """Run a deterministic in-memory replay through the Secret Ingredients path."""

    def __init__(
        self,
        *,
        scorer: SecretCandidateScorer,
        max_active: int,
        max_queue_size: int,
    ) -> None:
        self._scorer = scorer
        self._max_active = max_active
        self._max_queue_size = max_queue_size

    async def run(self, quotes: list[Quote]) -> SecretReplayValidationResult:
        feature_engine = L1FeatureEngine()
        handoff_manager = SecretSauceHandoffManager()
        queue = L2PromotionQueue(
            _ReplayL2Manager(),
            max_active=self._max_active,
            max_queue_size=self._max_queue_size,
        )

        for quote in sorted(quotes, key=lambda item: item.timestamp):
            feature_engine.ingest(quote)

        snapshots = feature_engine.snapshots()
        candidates = self._scorer.score_snapshots(snapshots)
        handoffs = handoff_manager.emit(candidates)
        queue.enqueue(handoffs)
        promoted_tickers = await queue.drain_once()

        return SecretReplayValidationResult(
            snapshots=[self._serialize_snapshot(snapshot) for snapshot in snapshots],
            candidates=[self._serialize_candidate(candidate) for candidate in candidates],
            handoffs=[handoff.to_dict() for handoff in handoffs],
            queue=queue.snapshot(),
            promoted_tickers=promoted_tickers,
        )

    @staticmethod
    def _serialize_snapshot(snapshot) -> dict:
        return {
            "ticker": snapshot.ticker,
            "price_velocity_1m": snapshot.price_velocity_1m,
            "spread_pct": snapshot.spread_pct,
            "quote_rate": snapshot.quote_rate,
            "volume_expansion": snapshot.volume_expansion,
            "buy_pressure": snapshot.buy_pressure,
            "last_price": snapshot.last_price,
            "last_updated": snapshot.last_updated.isoformat(),
        }

    @staticmethod
    def _serialize_candidate(candidate) -> dict:
        return {
            "ticker": candidate.ticker,
            "score": candidate.breakout_score,
            "price_velocity_1m": candidate.pct_change_1m,
            "pct_change_5m": candidate.pct_change_5m,
            "volume_expansion": candidate.volume_ratio,
            "spread_pct": candidate.spread_pct,
            "quote_rate": candidate.quote_rate,
            "buy_pressure": candidate.buy_pressure,
            "reason_flags": list(candidate.reason_flags),
            "timestamp": candidate.timestamp.isoformat(),
        }


def build_replay_quote(
    *,
    ticker: str,
    bid: float,
    ask: float,
    last: float,
    volume: int,
    timestamp: datetime,
) -> Quote:
    return Quote(
        ticker=ticker,
        bid=bid,
        ask=ask,
        last=last,
        volume=volume,
        timestamp=timestamp,
    )
