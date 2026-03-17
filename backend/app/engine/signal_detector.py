"""Heuristic breakout signal detector — 5 microstructure features."""

from dataclasses import dataclass
from enum import Enum

from app.data.tick_buffer import MarketSnapshot, TickBuffer
from app.core.logging import get_logger

log = get_logger(__name__)


class SignalType(str, Enum):
    BREAKOUT = "breakout"
    FALSE_BREAKOUT = "false_breakout"


@dataclass
class FeatureVector:
    """Computed feature set for a single ticker at a point in time."""

    ticker: str
    liquidity_imbalance: float
    spread_compression: float
    bid_stacking: float
    volume_acceleration: float
    order_aggression: float
    composite_score: float
    signal_type: SignalType
    ml_confidence: float | None = None


class SignalDetector:
    """Computes 5 microstructure features and a composite breakout score.

    Each feature is normalized to [0, 1]. A weighted composite >= threshold
    triggers a BREAKOUT signal.
    """

    # Feature weights (must sum to 1.0)
    WEIGHTS = {
        "liquidity_imbalance": 0.25,
        "spread_compression": 0.15,
        "bid_stacking": 0.20,
        "volume_acceleration": 0.20,
        "order_aggression": 0.20,
    }
    THRESHOLD = 0.65

    def __init__(self, tick_buffer: TickBuffer, minimum_history: int = 10, ml_scorer=None) -> None:
        self.tick_buffer = tick_buffer
        self.minimum_history = minimum_history
        self.ml_scorer = ml_scorer

    def compute_signal(self, ticker: str) -> FeatureVector | None:
        """Compute the feature vector for a ticker. Returns None if insufficient data."""
        if not self.tick_buffer.has_minimum_history(ticker, self.minimum_history):
            return None

        history = self.tick_buffer.get_history(ticker)
        latest = history[-1]

        li = self._liquidity_imbalance(latest)
        sc = self._spread_compression(latest, history)
        bs = self._bid_stacking(latest)
        va = self._volume_acceleration(latest, history)
        oa = self._order_aggression(history)

        rule_score = (
            self.WEIGHTS["liquidity_imbalance"] * li
            + self.WEIGHTS["spread_compression"] * sc
            + self.WEIGHTS["bid_stacking"] * bs
            + self.WEIGHTS["volume_acceleration"] * va
            + self.WEIGHTS["order_aggression"] * oa
        )

        # Hybrid ML scoring (if available)
        ml_confidence = None
        score = rule_score
        if self.ml_scorer is not None:
            fv = FeatureVector(
                ticker=ticker,
                liquidity_imbalance=round(li, 4),
                spread_compression=round(sc, 4),
                bid_stacking=round(bs, 4),
                volume_acceleration=round(va, 4),
                order_aggression=round(oa, 4),
                composite_score=round(rule_score, 4),
                signal_type=SignalType.FALSE_BREAKOUT,  # placeholder
            )
            score, ml_confidence = self.ml_scorer.score(fv)

        signal_type = SignalType.BREAKOUT if score >= self.THRESHOLD else SignalType.FALSE_BREAKOUT

        return FeatureVector(
            ticker=ticker,
            liquidity_imbalance=round(li, 4),
            spread_compression=round(sc, 4),
            bid_stacking=round(bs, 4),
            volume_acceleration=round(va, 4),
            order_aggression=round(oa, 4),
            composite_score=round(score, 4),
            signal_type=signal_type,
            ml_confidence=ml_confidence,
        )

    # ── Feature 1: Liquidity Imbalance ──────────────────────────────
    @staticmethod
    def _liquidity_imbalance(snap: MarketSnapshot) -> float:
        """Bid vs ask volume ratio from the order book.

        High value → more bid-side liquidity → bullish pressure.
        """
        bids = snap.order_book.bids
        asks = snap.order_book.asks
        if not bids or not asks:
            return 0.5

        total_bid = sum(level.size for level in bids)
        total_ask = sum(level.size for level in asks)
        total = total_bid + total_ask
        if total == 0:
            return 0.5

        # ratio in [0, 1]: >0.5 means bid-heavy
        return min(1.0, max(0.0, total_bid / total))

    # ── Feature 2: Spread Compression ───────────────────────────────
    @staticmethod
    def _spread_compression(latest: MarketSnapshot, history: list[MarketSnapshot]) -> float:
        """Current spread narrowness vs rolling average.

        Tight spread relative to history → higher score.
        """
        current_spread = latest.quote.ask - latest.quote.bid
        if current_spread <= 0:
            return 1.0

        spreads = [s.quote.ask - s.quote.bid for s in history]
        avg_spread = sum(spreads) / len(spreads)
        if avg_spread <= 0:
            return 1.0

        ratio = current_spread / avg_spread
        # ratio < 1 → compressed → high score; ratio > 1 → widened → low score
        return min(1.0, max(0.0, 1.0 - (ratio - 0.5)))

    # ── Feature 3: Bid Stacking ─────────────────────────────────────
    @staticmethod
    def _bid_stacking(snap: MarketSnapshot) -> float:
        """Top-3 bid level size concentration relative to full book.

        Large bids stacked near the top → support / accumulation.
        """
        bids = snap.order_book.bids
        if len(bids) < 3:
            return 0.0

        top3_size = sum(level.size for level in bids[:3])
        total_size = sum(level.size for level in bids)
        if total_size == 0:
            return 0.0

        concentration = top3_size / total_size
        # Normalize: typical concentration ~0.3; high is ~0.6+
        return min(1.0, max(0.0, concentration * 1.5))

    # ── Feature 4: Volume Acceleration ──────────────────────────────
    @staticmethod
    def _volume_acceleration(latest: MarketSnapshot, history: list[MarketSnapshot]) -> float:
        """Current volume vs average historical volume.

        Spike in volume → elevated interest → higher score.
        """
        current_vol = latest.quote.volume
        if current_vol == 0:
            return 0.0

        avg_vol = sum(s.quote.volume for s in history) / len(history)
        if avg_vol == 0:
            return 1.0

        ratio = current_vol / avg_vol
        # ratio 1.0 → normal; 2.0+ → strong acceleration
        return min(1.0, max(0.0, (ratio - 0.5) / 1.5))

    # ── Feature 5: Order Aggression ─────────────────────────────────
    @staticmethod
    def _order_aggression(history: list[MarketSnapshot]) -> float:
        """Ask depletion + bid growth over recent snapshots.

        Shrinking asks + growing bids → aggressive buying.
        """
        if len(history) < 2:
            return 0.5

        recent = history[-5:]  # last 5 ticks
        if len(recent) < 2:
            return 0.5

        first = recent[0]
        last = recent[-1]

        first_ask_total = sum(l.size for l in first.order_book.asks) if first.order_book.asks else 1
        last_ask_total = sum(l.size for l in last.order_book.asks) if last.order_book.asks else 1
        first_bid_total = sum(l.size for l in first.order_book.bids) if first.order_book.bids else 1
        last_bid_total = sum(l.size for l in last.order_book.bids) if last.order_book.bids else 1

        # Ask depletion: asks shrinking → bullish (score from 0 to 0.5)
        ask_ratio = last_ask_total / first_ask_total if first_ask_total else 1.0
        ask_score = min(0.5, max(0.0, (1.0 - ask_ratio) * 0.5 + 0.25))

        # Bid growth: bids growing → bullish (score from 0 to 0.5)
        bid_ratio = last_bid_total / first_bid_total if first_bid_total else 1.0
        bid_score = min(0.5, max(0.0, (bid_ratio - 1.0) * 0.5 + 0.25))

        return min(1.0, max(0.0, ask_score + bid_score))
