"""Strict L2 execution gate used before transmitting entry orders."""

from dataclasses import dataclass

from app.core.config import settings
from app.data.tick_buffer import MarketSnapshot
from app.engine.l2_pattern_engine import L2PatternEngine


@dataclass
class ExecutionGateDecision:
    """Go/no-go decision for entry transmission."""

    allowed: bool
    reason: str | None = None


class L2ExecutionGate:
    """Reject entries when L2 quality is not good enough for transmission."""

    def __init__(self, pattern_engine: L2PatternEngine | None = None) -> None:
        self.pattern_engine = pattern_engine or L2PatternEngine()

    def evaluate(self, snapshot: MarketSnapshot) -> ExecutionGateDecision:
        if snapshot.order_book is None:
            return ExecutionGateDecision(allowed=False, reason="missing_l2")

        quote = snapshot.quote
        if quote.ask <= 0 or quote.bid <= 0:
            return ExecutionGateDecision(allowed=False, reason="invalid_quote")

        spread_pct = (quote.ask - quote.bid) / max(quote.ask, 0.01)
        if spread_pct > settings.execution_gate_max_spread_pct:
            return ExecutionGateDecision(allowed=False, reason="spread_too_wide")

        pattern = self.pattern_engine.analyze(snapshot.order_book)
        if pattern is None:
            return ExecutionGateDecision(allowed=False, reason="missing_l2")

        if pattern.bid_stacking < settings.execution_gate_min_bid_stacking:
            return ExecutionGateDecision(allowed=False, reason="weak_bid_stack")

        if self._seller_overhead_pressure(snapshot) > settings.execution_gate_max_seller_pressure:
            return ExecutionGateDecision(allowed=False, reason="seller_wall_overhead")

        if pattern.momentum_confirmation < settings.execution_gate_min_buying_aggression:
            return ExecutionGateDecision(allowed=False, reason="insufficient_buying_aggression")

        support_stability = 1.0 - pattern.spoofing_score
        if support_stability < settings.execution_gate_min_support_stability:
            return ExecutionGateDecision(allowed=False, reason="unstable_support")

        return ExecutionGateDecision(allowed=True)

    @staticmethod
    def _seller_overhead_pressure(snapshot: MarketSnapshot) -> float:
        order_book = snapshot.order_book
        if order_book is None or not order_book.bids or not order_book.asks:
            return 999.0

        overhead_asks = sum(level.size for level in order_book.asks[:3])
        supporting_bids = sum(level.size for level in order_book.bids[:3])
        if supporting_bids <= 0:
            return 999.0
        return overhead_asks / supporting_bids
