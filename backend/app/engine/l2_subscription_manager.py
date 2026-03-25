"""Dynamic lifecycle manager for IBKR L2 depth subscriptions."""

import time
from dataclasses import dataclass, field

from app.broker.interface import BrokerInterface, OrderBook
from app.core.logging import get_logger

log = get_logger(__name__)


@dataclass
class L2Subscription:
    ticker: str
    subscribed_at: float
    confirmed: bool = False
    last_order_book: OrderBook | None = None
    last_updated_at: float = field(default_factory=time.monotonic)


class L2SubscriptionManager:
    """Track active L2 depth subscriptions and their expiry lifecycle."""

    def __init__(
        self,
        broker: BrokerInterface,
        timeout_seconds: float = 30.0,
        clock=time.monotonic,
    ) -> None:
        self._broker = broker
        self._timeout_seconds = timeout_seconds
        self._clock = clock
        self._active: dict[str, L2Subscription] = {}
        self.active_symbols: set[str] = set()

    async def subscribe(self, ticker: str) -> bool:
        """Subscribe to L2 depth for a symbol if not already active."""
        if ticker in self._active:
            return False

        await self._broker.subscribe_l2_depth(ticker)
        now = self._clock()
        self._active[ticker] = L2Subscription(ticker=ticker, subscribed_at=now, last_updated_at=now)
        self.active_symbols.add(ticker)
        log.info("l2_manager.subscribed", ticker=ticker, active=len(self.active_symbols))
        return True

    async def unsubscribe(self, ticker: str) -> bool:
        """Cancel an active L2 subscription if present."""
        record = self._active.pop(ticker, None)
        was_active = record is not None or ticker in self.active_symbols
        self.active_symbols.discard(ticker)
        if not was_active:
            return False

        await self._broker.unsubscribe_l2_depth(ticker)
        log.info("l2_manager.unsubscribed", ticker=ticker, active=len(self.active_symbols))
        return record is not None

    def is_active(self, ticker: str) -> bool:
        return ticker in self._active

    def mark_confirmed(self, ticker: str) -> None:
        record = self._active.get(ticker)
        if record is None:
            return
        record.confirmed = True
        record.last_updated_at = self._clock()
        log.info("l2_manager.confirmed", ticker=ticker)

    async def get_order_book(self, ticker: str) -> OrderBook | None:
        """Fetch and cache the current order book for an active symbol."""
        if ticker not in self._active:
            return None
        order_book = await self._broker.get_order_book(ticker)
        record = self._active[ticker]
        record.last_order_book = order_book
        record.last_updated_at = self._clock()
        return order_book

    async def cleanup_expired(self) -> list[str]:
        """Unsubscribe non-confirmed symbols whose tracking window expired."""
        now = self._clock()
        expired = [
            ticker
            for ticker, record in self._active.items()
            if not record.confirmed and (now - record.subscribed_at) >= self._timeout_seconds
        ]
        for ticker in expired:
            await self.unsubscribe(ticker)
        if expired:
            log.info("l2_manager.expired", count=len(expired), tickers=expired)
        return expired

    async def on_reconnect(self) -> None:
        """Re-subscribe all currently active symbols after broker reconnect."""
        for ticker in list(self.active_symbols):
            await self._broker.subscribe_l2_depth(ticker)
        if self.active_symbols:
            log.info("l2_manager.resubscribed", count=len(self.active_symbols))
