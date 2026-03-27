"""L2 pattern recognition engine for order book confirmation signals."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from app.broker.interface import OrderBook


class PatternType(str, Enum):
    IMBALANCE = "imbalance"
    BID_STACKING = "bid_stacking"
    SPOOFING = "spoofing"
    MOMENTUM_CONFIRMATION = "momentum_confirmation"
    MIXED = "mixed"


@dataclass
class L2PatternSignal:
    symbol: str
    confidence_score: float
    pattern_type: PatternType
    timestamp: datetime = field(default_factory=datetime.now)
    liquidity_imbalance: float = 0.0
    bid_stacking: float = 0.0
    spoofing_score: float = 0.0
    momentum_confirmation: float = 0.0


class L2PatternEngine:
    """Fast stateless L2 pattern scorer for one order book at a time."""

    WEIGHTS = {
        "liquidity_imbalance": 0.35,
        "bid_stacking": 0.25,
        "spoofing_score": 0.15,
        "momentum_confirmation": 0.25,
    }

    def analyze(self, order_book: OrderBook | None) -> L2PatternSignal | None:
        if order_book is None:
            return None

        li = self._liquidity_imbalance(order_book)
        bs = self._bid_stacking(order_book)
        spoof = self._spoofing_score(order_book)
        momentum = self._momentum_confirmation(order_book)

        score = min(
            1.0,
            self.WEIGHTS["liquidity_imbalance"] * li
            + self.WEIGHTS["bid_stacking"] * bs
            + self.WEIGHTS["spoofing_score"] * spoof
            + self.WEIGHTS["momentum_confirmation"] * momentum,
        )

        return L2PatternSignal(
            symbol=order_book.ticker,
            confidence_score=round(score, 4),
            pattern_type=self._pattern_type(li, bs, spoof, momentum),
            liquidity_imbalance=round(li, 4),
            bid_stacking=round(bs, 4),
            spoofing_score=round(spoof, 4),
            momentum_confirmation=round(momentum, 4),
        )

    @staticmethod
    def _liquidity_imbalance(order_book: OrderBook) -> float:
        bids = order_book.bids
        asks = order_book.asks
        if not bids or not asks:
            return 0.0
        total_bid = sum(level.size for level in bids)
        total_ask = sum(level.size for level in asks)
        total = total_bid + total_ask
        if total == 0:
            return 0.0
        return max(0.0, min(1.0, total_bid / total))

    @staticmethod
    def _bid_stacking(order_book: OrderBook) -> float:
        bids = order_book.bids
        if len(bids) < 3:
            return 0.0
        top_three = sum(level.size for level in bids[:3])
        total_bid = sum(level.size for level in bids)
        if total_bid == 0:
            return 0.0
        concentration = top_three / total_bid
        return max(0.0, min(1.0, concentration * 1.5))

    @staticmethod
    def _spoofing_score(order_book: OrderBook) -> float:
        bids = order_book.bids
        asks = order_book.asks
        if len(bids) < 2 or len(asks) < 2:
            return 0.0

        largest_bid = max(level.size for level in bids)
        average_bid = sum(level.size for level in bids) / len(bids)
        largest_ask = max(level.size for level in asks)
        average_ask = sum(level.size for level in asks) / len(asks)

        bid_wall = largest_bid / average_bid if average_bid else 1.0
        ask_wall = largest_ask / average_ask if average_ask else 1.0
        wall_ratio = max(bid_wall, ask_wall)

        # A large isolated wall can indicate suspicious liquidity.
        return max(0.0, min(1.0, (wall_ratio - 1.0) / 5.0))

    @staticmethod
    def _momentum_confirmation(order_book: OrderBook) -> float:
        bids = order_book.bids
        asks = order_book.asks
        if not bids or not asks:
            return 0.0

        top_bid = bids[0]
        top_ask = asks[0]
        spread = top_ask.price - top_bid.price
        if spread <= 0:
            return 1.0

        top_bid_size = top_bid.size
        top_ask_size = top_ask.size
        if top_bid_size + top_ask_size == 0:
            return 0.0

        size_pressure = top_bid_size / (top_bid_size + top_ask_size)
        spread_bonus = max(0.0, min(1.0, 1.0 - spread / max(top_ask.price, 0.01)))
        return max(0.0, min(1.0, (size_pressure * 0.7) + (spread_bonus * 0.3)))

    @staticmethod
    def _pattern_type(
        liquidity_imbalance: float,
        bid_stacking: float,
        spoofing_score: float,
        momentum_confirmation: float,
    ) -> PatternType:
        scores = {
            PatternType.IMBALANCE: liquidity_imbalance,
            PatternType.BID_STACKING: bid_stacking,
            PatternType.SPOOFING: spoofing_score,
            PatternType.MOMENTUM_CONFIRMATION: momentum_confirmation,
        }
        best_pattern, best_score = max(scores.items(), key=lambda item: item[1])
        second_best = sorted(scores.values(), reverse=True)[1]
        if best_score - second_best < 0.1:
            return PatternType.MIXED
        return best_pattern
