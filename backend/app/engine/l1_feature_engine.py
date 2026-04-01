"""Dedicated rolling L1 hot-state engine for Secret Ingredients."""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.broker.interface import Quote


@dataclass
class L1FeatureSnapshot:
    ticker: str
    price_velocity_1m: float
    spread_pct: float
    quote_rate: float
    volume_expansion: float
    buy_pressure: float
    last_price: float
    last_updated: datetime


@dataclass
class SymbolL1State:
    ticker: str
    quotes: deque[Quote] = field(default_factory=lambda: deque(maxlen=600))

    def push(self, quote: Quote) -> None:
        self.quotes.append(quote)

    def _quotes_since(self, seconds: int) -> list[Quote]:
        cutoff = self.quotes[-1].timestamp - timedelta(seconds=seconds)
        return [quote for quote in self.quotes if quote.timestamp >= cutoff]

    def price_velocity(self, seconds: int = 60) -> float:
        if len(self.quotes) < 2:
            return 0.0
        recent = self._quotes_since(seconds)
        baseline = recent[0] if recent else self.quotes[0]
        current = self.quotes[-1]
        if baseline.last == 0:
            return 0.0
        return ((current.last - baseline.last) / baseline.last) * 100

    def spread_pct(self) -> float:
        if not self.quotes:
            return 0.0
        latest = self.quotes[-1]
        midpoint = (latest.bid + latest.ask) / 2 if (latest.bid + latest.ask) else latest.last
        if midpoint <= 0:
            return 0.0
        spread = max(0.0, latest.ask - latest.bid)
        return spread / midpoint

    def quote_rate(self, seconds: int = 15) -> float:
        if not self.quotes:
            return 0.0
        recent = self._quotes_since(seconds)
        window = max(seconds, 1)
        return len(recent) / window

    def volume_expansion(self, recent_seconds: int = 60, baseline_seconds: int = 300) -> float:
        if len(self.quotes) < 2:
            return 1.0

        recent = self._quotes_since(recent_seconds)
        baseline = self._quotes_since(baseline_seconds)
        if not baseline:
            return 1.0

        recent_volume = sum(max(quote.volume, 0) for quote in recent)
        baseline_volume = sum(max(quote.volume, 0) for quote in baseline)
        baseline_rate = baseline_volume / max(baseline_seconds, 1)
        expected_recent_volume = baseline_rate * recent_seconds
        if expected_recent_volume <= 0:
            return 1.0
        return recent_volume / expected_recent_volume

    def buy_pressure(self, seconds: int = 30) -> float:
        recent = self._quotes_since(seconds)
        if len(recent) < 2:
            return 0.0

        positive_bid_moves = 0
        compressing_spread_moves = 0
        non_negative_ask_moves = 0
        transitions = 0
        for previous, current in zip(recent, recent[1:]):
            transitions += 1
            if current.bid >= previous.bid:
                positive_bid_moves += 1
            if (current.ask - current.bid) <= (previous.ask - previous.bid):
                compressing_spread_moves += 1
            if current.ask <= previous.ask:
                non_negative_ask_moves += 1

        if transitions == 0:
            return 0.0

        score = (
            0.45 * (positive_bid_moves / transitions)
            + 0.35 * (compressing_spread_moves / transitions)
            + 0.20 * (non_negative_ask_moves / transitions)
        )
        return min(1.0, max(0.0, score))


class L1FeatureEngine:
    """Maintain dedicated rolling L1 hot state and expose feature snapshots."""

    def __init__(self) -> None:
        self._states: dict[str, SymbolL1State] = {}

    def ingest(self, quote: Quote) -> None:
        state = self._states.setdefault(quote.ticker, SymbolL1State(ticker=quote.ticker))
        state.push(quote)

    async def ingest_from_cache(self, cache, tickers: list[str]) -> None:
        for ticker in tickers:
            quote = await cache.get_l1(ticker)
            if quote is not None:
                self.ingest(quote)

    def snapshot(self, ticker: str) -> L1FeatureSnapshot | None:
        state = self._states.get(ticker)
        if state is None or not state.quotes:
            return None
        latest = state.quotes[-1]
        return L1FeatureSnapshot(
            ticker=ticker,
            price_velocity_1m=round(state.price_velocity(60), 4),
            spread_pct=round(state.spread_pct(), 6),
            quote_rate=round(state.quote_rate(15), 4),
            volume_expansion=round(state.volume_expansion(60, 300), 4),
            buy_pressure=round(state.buy_pressure(30), 4),
            last_price=latest.last,
            last_updated=latest.timestamp,
        )

    def snapshots(self, tickers: list[str] | None = None) -> list[L1FeatureSnapshot]:
        scan_tickers = tickers or list(self._states.keys())
        result: list[L1FeatureSnapshot] = []
        for ticker in scan_tickers:
            snapshot = self.snapshot(ticker)
            if snapshot is not None:
                result.append(snapshot)
        return result

    @property
    def active_symbols(self) -> int:
        return len(self._states)
