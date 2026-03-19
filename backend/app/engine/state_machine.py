"""5-stage pre-trade state machine: Normal -> Watching -> Candidate -> L2 Confirm -> ReadyToBuy."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from app.broker.interface import BrokerInterface
from app.core.config import settings
from app.core.logging import get_logger
from app.core.metrics import STATE_TRANSITIONS
from app.data.tick_buffer import TickBuffer
from app.engine.signal_detector import FeatureVector, SignalDetector

log = get_logger(__name__)


class SymbolStage(str, Enum):
    """Progressive pre-trade pipeline stages."""

    NORMAL = "normal"
    WATCHING = "watching"
    CANDIDATE = "candidate"
    L2_CONFIRM = "l2_confirm"
    READY_TO_BUY = "ready_to_buy"

    @property
    def rank(self) -> int:
        return _STAGE_RANK[self]


_STAGE_RANK = {
    SymbolStage.NORMAL: 0,
    SymbolStage.WATCHING: 1,
    SymbolStage.CANDIDATE: 2,
    SymbolStage.L2_CONFIRM: 3,
    SymbolStage.READY_TO_BUY: 4,
}


@dataclass
class TickerState:
    """In-memory state for a single ticker in the pipeline."""

    ticker: str
    stage: SymbolStage = SymbolStage.NORMAL
    entered_at: datetime = field(default_factory=datetime.now)
    score: float = 0.0
    feature_vector: FeatureVector | None = None
    consecutive_ticks: int = 0
    decay_ticks: int = 0
    reason: str = ""


class StateMachine:
    """Manages per-ticker progression through the 5-stage pre-trade pipeline.

    Sits between SignalDetector (which computes features) and TradeExecutor
    (which handles order execution). A ticker must progress through all stages
    before it becomes actionable.
    """

    # Minimum consecutive ticks at a stage before promotion
    CONFIRM_TICKS = 2

    def __init__(
        self,
        tick_buffer: TickBuffer,
        signal_detector: SignalDetector,
        broker: BrokerInterface,
    ) -> None:
        self.tick_buffer = tick_buffer
        self.signal_detector = signal_detector
        self.broker = broker
        self._states: dict[str, TickerState] = {}
        self._l2_subscribed: set[str] = set()

    def get_state(self, ticker: str) -> TickerState:
        if ticker not in self._states:
            self._states[ticker] = TickerState(ticker=ticker)
        return self._states[ticker]

    def all_states(self) -> list[TickerState]:
        return list(self._states.values())

    def get_ready_to_buy(self) -> list[TickerState]:
        return [s for s in self._states.values() if s.stage == SymbolStage.READY_TO_BUY]

    async def evaluate(self, ticker: str) -> TickerState:
        """Compute features for a ticker and apply state transition logic.

        Returns the updated TickerState (never None).
        """
        state = self.get_state(ticker)
        feature = self.signal_detector.compute_signal(ticker)

        if feature is None:
            return state

        state.score = feature.composite_score
        state.feature_vector = feature

        await self._apply_transitions(state, feature)
        return state

    async def _apply_transitions(self, state: TickerState, fv: FeatureVector) -> None:
        """Evaluate promotion or demotion based on score and L2 features."""
        score = fv.composite_score
        stage = state.stage

        # Determine the target stage based on current score
        target = self._target_stage(score, fv)

        if target.rank > stage.rank:
            # Promoting — require consecutive confirmation ticks
            state.consecutive_ticks += 1
            state.decay_ticks = 0

            if state.consecutive_ticks >= self.CONFIRM_TICKS or stage == SymbolStage.NORMAL:
                # Promote one stage at a time
                next_stage = self._next_stage(stage)
                if next_stage is not None and next_stage.rank <= target.rank:
                    await self._transition(state, next_stage, fv)
        elif target.rank < stage.rank:
            # Demoting — allow decay_ticks before dropping
            state.decay_ticks += 1
            state.consecutive_ticks = 0

            if state.decay_ticks >= settings.state_decay_ticks:
                # Drop one stage at a time
                prev = self._prev_stage(stage)
                if prev is not None:
                    await self._transition(state, prev, fv)
        else:
            # Holding steady at current stage
            state.consecutive_ticks += 1
            state.decay_ticks = 0

    def _target_stage(self, score: float, fv: FeatureVector) -> SymbolStage:
        """Determine which stage a ticker qualifies for based on score + L2."""
        if score >= settings.state_ready_to_buy_threshold and self._l2_confirmed(fv):
            return SymbolStage.READY_TO_BUY
        if score >= settings.state_l2_confirm_threshold:
            return SymbolStage.L2_CONFIRM
        if score >= settings.state_candidate_threshold:
            return SymbolStage.CANDIDATE
        if score >= settings.state_watching_threshold:
            return SymbolStage.WATCHING
        return SymbolStage.NORMAL

    def _l2_confirmed(self, fv: FeatureVector) -> bool:
        """Check L2 order book features meet confirmation thresholds."""
        return (
            fv.bid_stacking >= settings.state_l2_bid_stacking_min
            and fv.liquidity_imbalance >= settings.state_l2_liquidity_imbalance_min
            and fv.order_aggression >= settings.state_l2_order_aggression_min
            and fv.spread_compression >= settings.state_l2_spread_compression_min
        )

    async def _transition(
        self, state: TickerState, new_stage: SymbolStage, fv: FeatureVector
    ) -> None:
        old_stage = state.stage
        state.stage = new_stage
        state.entered_at = datetime.now()
        state.consecutive_ticks = 0
        state.decay_ticks = 0
        state.reason = self._build_reason(old_stage, new_stage, fv)

        STATE_TRANSITIONS.labels(from_state=old_stage.value, to_state=new_stage.value).inc()

        log.info(
            "state_machine.transition",
            ticker=state.ticker,
            from_stage=old_stage.value,
            to_stage=new_stage.value,
            score=fv.composite_score,
            reason=state.reason,
        )

        # Manage L2 subscriptions
        if new_stage == SymbolStage.CANDIDATE and state.ticker not in self._l2_subscribed:
            await self.broker.subscribe_l2_depth(state.ticker)
            self._l2_subscribed.add(state.ticker)
        elif new_stage == SymbolStage.NORMAL and state.ticker in self._l2_subscribed:
            await self.broker.unsubscribe_l2_depth(state.ticker)
            self._l2_subscribed.discard(state.ticker)

    @staticmethod
    def _next_stage(stage: SymbolStage) -> SymbolStage | None:
        order = [
            SymbolStage.NORMAL,
            SymbolStage.WATCHING,
            SymbolStage.CANDIDATE,
            SymbolStage.L2_CONFIRM,
            SymbolStage.READY_TO_BUY,
        ]
        idx = order.index(stage)
        return order[idx + 1] if idx + 1 < len(order) else None

    @staticmethod
    def _prev_stage(stage: SymbolStage) -> SymbolStage | None:
        order = [
            SymbolStage.NORMAL,
            SymbolStage.WATCHING,
            SymbolStage.CANDIDATE,
            SymbolStage.L2_CONFIRM,
            SymbolStage.READY_TO_BUY,
        ]
        idx = order.index(stage)
        return order[idx - 1] if idx > 0 else None

    @staticmethod
    def _build_reason(
        old: SymbolStage, new: SymbolStage, fv: FeatureVector
    ) -> str:
        direction = "promoted" if new.rank > old.rank else "demoted"
        parts = [
            f"{direction} {old.value}->{new.value}",
            f"score={fv.composite_score:.2f}",
        ]
        if new.rank >= SymbolStage.L2_CONFIRM.rank:
            parts.append(
                f"L2(bid_stack={fv.bid_stacking:.2f} liq={fv.liquidity_imbalance:.2f} "
                f"aggr={fv.order_aggression:.2f} spread={fv.spread_compression:.2f})"
            )
        return " | ".join(parts)
