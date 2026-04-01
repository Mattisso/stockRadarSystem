"""Queue handoffs from Secret Ingredients into L2 subscription slots."""

from dataclasses import dataclass
from time import monotonic

from app.core.logging import get_logger
from app.engine.l2_subscription_manager import L2SubscriptionManager
from app.engine.secret_sauce_handoff import SecretSauceHandoff

log = get_logger(__name__)


@dataclass
class L2PromotionItem:
    ticker: str
    score: float
    queued_at: float
    handoff: SecretSauceHandoff


@dataclass
class ActiveL2Slot:
    ticker: str
    score: float
    promoted_at: float
    confirmed: bool = False


class L2PromotionQueue:
    """Bounded, score-prioritized queue feeding symbols into L2 tracking."""

    def __init__(
        self,
        l2_manager: L2SubscriptionManager,
        *,
        max_active: int = 8,
        max_queue_size: int = 100,
        clock=monotonic,
    ) -> None:
        self._l2_manager = l2_manager
        self._max_active = max(1, max_active)
        self._max_queue_size = max(1, max_queue_size)
        self._clock = clock
        self._queue: list[L2PromotionItem] = []
        self._active_slots: dict[str, ActiveL2Slot] = {}

    def enqueue(self, handoffs: list[SecretSauceHandoff]) -> int:
        added = 0
        active = self._l2_manager.active_symbols
        queued = {item.ticker for item in self._queue}

        for handoff in handoffs:
            if handoff.ticker in active or handoff.ticker in queued:
                continue
            item = L2PromotionItem(
                ticker=handoff.ticker,
                score=handoff.score,
                queued_at=self._clock(),
                handoff=handoff,
            )
            self._queue.append(item)
            queued.add(handoff.ticker)
            added += 1

        self._queue.sort(key=lambda item: item.score, reverse=True)
        if len(self._queue) > self._max_queue_size:
            self._queue = self._queue[: self._max_queue_size]

        if added:
            log.info("l2_promotion_queue.enqueued", added=added, depth=len(self._queue))
        return added

    async def drain_once(self) -> list[str]:
        self._prune_inactive_slots()
        promoted: list[str] = []
        while self._queue and len(self._l2_manager.active_symbols) < self._max_active:
            item = self._queue.pop(0)
            subscribed = await self._l2_manager.subscribe(item.ticker)
            if subscribed:
                self._active_slots[item.ticker] = ActiveL2Slot(
                    ticker=item.ticker,
                    score=item.score,
                    promoted_at=self._clock(),
                )
                promoted.append(item.ticker)
        while self._queue:
            weakest = self._weakest_replaceable_active()
            challenger = self._queue[0]
            if weakest is None or challenger.score <= weakest.score:
                break

            await self._l2_manager.unsubscribe(weakest.ticker)
            self._active_slots.pop(weakest.ticker, None)
            item = self._queue.pop(0)
            subscribed = await self._l2_manager.subscribe(item.ticker)
            if subscribed:
                self._active_slots[item.ticker] = ActiveL2Slot(
                    ticker=item.ticker,
                    score=item.score,
                    promoted_at=self._clock(),
                )
                promoted.append(item.ticker)
        if promoted:
            log.info(
                "l2_promotion_queue.promoted",
                count=len(promoted),
                active=len(self._l2_manager.active_symbols),
                queue_depth=len(self._queue),
                tickers=promoted,
            )
        return promoted

    def remove(self, ticker: str) -> bool:
        initial = len(self._queue)
        self._queue = [item for item in self._queue if item.ticker != ticker]
        return len(self._queue) != initial

    def mark_confirmed(self, ticker: str) -> None:
        slot = self._active_slots.get(ticker)
        if slot is not None:
            slot.confirmed = True

    def drop_stale_or_invalidated(self) -> list[str]:
        removed: list[str] = []
        active = set(self._l2_manager.active_symbols)
        for ticker in list(self._active_slots):
            if ticker not in active:
                self._active_slots.pop(ticker, None)
                removed.append(ticker)
        return removed

    def snapshot(self) -> dict:
        self._prune_inactive_slots()
        return {
            "active_count": len(self._l2_manager.active_symbols),
            "active_tickers": sorted(self._l2_manager.active_symbols),
            "queue_depth": len(self._queue),
            "queued_tickers": [item.ticker for item in self._queue],
            "max_active": self._max_active,
            "max_queue_size": self._max_queue_size,
            "replaceable_tickers": sorted(
                ticker for ticker, slot in self._active_slots.items() if not slot.confirmed
            ),
        }

    def _weakest_replaceable_active(self) -> ActiveL2Slot | None:
        replaceable = [
            slot
            for ticker, slot in self._active_slots.items()
            if ticker in self._l2_manager.active_symbols and not slot.confirmed
        ]
        if not replaceable:
            return None
        return min(replaceable, key=lambda slot: (slot.score, slot.promoted_at))

    def _prune_inactive_slots(self) -> None:
        active = set(self._l2_manager.active_symbols)
        for ticker in list(self._active_slots):
            if ticker not in active:
                self._active_slots.pop(ticker, None)
