"""L1 Breakout Detection Engine — fast pre-filter for 3000+ symbols.

Scans L1 data (price, volume) using rolling windows to detect early breakout
candidates. Candidates are passed to the state machine / signal detector for
deeper L2 analysis.

This is the first stage in the Arch v2.0 two-tier pipeline:
  BreakoutEngine (L1 scan) → StateMachine → SignalDetector (L1+L2) → TradeExecutor
"""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app.broker.interface import Quote
from app.core.logging import get_logger
from app.data.cache import CacheInterface

log = get_logger(__name__)


@dataclass
class L1Tick:
    """Lightweight L1 data point for rolling window."""

    price: float
    volume: int
    timestamp: datetime


@dataclass
class BreakoutEvent:
    """Emitted when a symbol crosses breakout thresholds."""

    ticker: str
    breakout_score: float
    pct_change_1m: float
    pct_change_5m: float
    volume_ratio: float
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SymbolTracker:
    """Per-symbol rolling state for breakout detection."""

    ticker: str
    ticks: deque = field(default_factory=lambda: deque(maxlen=300))  # ~5 min at 1/sec
    prev_close: float | None = None
    last_event_time: datetime | None = None

    # Cooldown: don't re-emit for the same symbol within this window
    COOLDOWN_SECONDS = 30

    def push(self, tick: L1Tick) -> None:
        self.ticks.append(tick)
        if self.prev_close is None:
            self.prev_close = tick.price

    def _clock_now(self) -> datetime:
        latest = self.ticks[-1].timestamp if self.ticks else None
        if latest is not None and latest.tzinfo is not None:
            return datetime.now(tz=timezone.utc)
        return datetime.now()

    def pct_change(self, seconds: int) -> float:
        """Percent change over the last N seconds."""
        if len(self.ticks) < 2:
            return 0.0
        cutoff = self._clock_now() - timedelta(seconds=seconds)
        baseline = None
        for t in self.ticks:
            if t.timestamp >= cutoff:
                baseline = t
                break
        if baseline is None or baseline.price == 0:
            return 0.0
        current = self.ticks[-1].price
        return ((current - baseline.price) / baseline.price) * 100

    def volume_ratio(self, seconds: int = 60) -> float:
        """Current minute volume vs average minute volume over rolling window."""
        now = self._clock_now()
        cutoff_recent = now - timedelta(seconds=seconds)
        cutoff_total = now - timedelta(seconds=300)  # 5 min window

        recent_vol = 0
        total_vol = 0
        total_ticks = 0

        for t in self.ticks:
            if t.timestamp >= cutoff_total:
                total_vol += t.volume
                total_ticks += 1
            if t.timestamp >= cutoff_recent:
                recent_vol += t.volume

        if total_ticks == 0 or total_vol == 0:
            return 1.0

        # Normalize: average per-tick volume * ticks in recent window
        avg_per_tick = total_vol / total_ticks
        recent_tick_count = sum(1 for t in self.ticks if t.timestamp >= cutoff_recent)
        expected = avg_per_tick * max(recent_tick_count, 1)

        if expected == 0:
            return 1.0
        return recent_vol / expected

    def can_emit(self) -> bool:
        if self.last_event_time is None:
            return True
        return (self._clock_now() - self.last_event_time).total_seconds() >= self.COOLDOWN_SECONDS


class BreakoutEngine:
    """Scans all universe symbols for L1 breakout signals.

    Designed for efficiency across 3000+ symbols. Each call to `scan()`
    evaluates every symbol and returns a list of breakout candidates.
    """

    # Score thresholds
    WATCHING_THRESHOLD = 0.3
    CANDIDATE_THRESHOLD = 0.6

    # Price change thresholds (%)
    STRONG_MOVE_PCT = 20.0
    EXTREME_MOVE_PCT = 50.0

    # Volume surge threshold (ratio vs average)
    VOLUME_SURGE_RATIO = 2.0

    def __init__(self, cache: CacheInterface | None = None) -> None:
        self._cache = cache
        self._trackers: dict[str, SymbolTracker] = {}

    def get_tracker(self, ticker: str) -> SymbolTracker:
        if ticker not in self._trackers:
            self._trackers[ticker] = SymbolTracker(ticker=ticker)
        return self._trackers[ticker]

    def ingest(self, quote: Quote) -> None:
        """Push a single L1 quote into the tracker. Called from Polygon consumer or scheduler."""
        tracker = self.get_tracker(quote.ticker)
        tracker.push(L1Tick(price=quote.last, volume=quote.volume, timestamp=quote.timestamp))

    async def ingest_from_cache(self, tickers: list[str]) -> None:
        """Pull latest L1 quotes from cache for all tickers."""
        if not self._cache:
            return
        for ticker in tickers:
            quote = await self._cache.get_l1(ticker)
            if quote:
                self.ingest(quote)

    def scan(self, tickers: list[str] | None = None) -> list[BreakoutEvent]:
        """Evaluate all tracked symbols and return breakout candidates.

        Returns events only for symbols that cross thresholds and are not
        in cooldown. Designed to be called every few seconds.
        """
        events: list[BreakoutEvent] = []
        scan_tickers = tickers or list(self._trackers.keys())

        for ticker in scan_tickers:
            tracker = self._trackers.get(ticker)
            if tracker is None or len(tracker.ticks) < 5:
                continue

            pct_1m = tracker.pct_change(60)
            pct_5m = tracker.pct_change(300)
            vol_ratio = tracker.volume_ratio(60)

            score = self._compute_score(pct_1m, pct_5m, vol_ratio)

            if score >= self.WATCHING_THRESHOLD and tracker.can_emit():
                event = BreakoutEvent(
                    ticker=ticker,
                    breakout_score=round(score, 4),
                    pct_change_1m=round(pct_1m, 2),
                    pct_change_5m=round(pct_5m, 2),
                    volume_ratio=round(vol_ratio, 2),
                )
                events.append(event)
                tracker.last_event_time = tracker._clock_now()

        return events

    def _compute_score(self, pct_1m: float, pct_5m: float, vol_ratio: float) -> float:
        """Weighted composite breakout score from L1 metrics. Returns 0.0–1.0."""

        # Price momentum score (0–0.5)
        # Uses the stronger of 1m or 5m change
        abs_pct = max(abs(pct_1m), abs(pct_5m) * 0.5)  # Weight 5m less
        if abs_pct >= self.EXTREME_MOVE_PCT:
            price_score = 0.5
        elif abs_pct >= self.STRONG_MOVE_PCT:
            price_score = 0.35
        elif abs_pct >= 5.0:
            price_score = 0.1 + (abs_pct - 5.0) / (self.STRONG_MOVE_PCT - 5.0) * 0.25
        else:
            price_score = abs_pct / 5.0 * 0.1

        # Volume surge score (0–0.5)
        if vol_ratio >= 5.0:
            vol_score = 0.5
        elif vol_ratio >= self.VOLUME_SURGE_RATIO:
            vol_score = 0.2 + (vol_ratio - self.VOLUME_SURGE_RATIO) / 3.0 * 0.3
        elif vol_ratio >= 1.2:
            vol_score = (vol_ratio - 1.0) / 1.0 * 0.2
        else:
            vol_score = 0.0

        return min(1.0, price_score + vol_score)

    @property
    def active_trackers(self) -> int:
        return len(self._trackers)
