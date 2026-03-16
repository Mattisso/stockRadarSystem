"""Broker abstraction layer — swap between MockBroker and IBKRBroker."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class Quote:
    """Current quote for a symbol."""

    ticker: str
    bid: float
    ask: float
    last: float
    volume: int
    timestamp: datetime


@dataclass
class OrderBookLevel:
    """Single price level in the order book."""

    price: float
    size: int
    order_count: int = 1


@dataclass
class OrderBook:
    """Level-2 order book snapshot."""

    ticker: str
    bids: list[OrderBookLevel] = field(default_factory=list)
    asks: list[OrderBookLevel] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class OrderResult:
    """Result of an order submission."""

    order_id: str
    ticker: str
    side: OrderSide
    quantity: int
    order_type: OrderType
    status: OrderStatus
    fill_price: float | None = None
    filled_quantity: int = 0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Position:
    """Current position in a symbol."""

    ticker: str
    quantity: int
    avg_cost: float
    market_value: float
    unrealized_pnl: float


@dataclass
class AccountSummary:
    """Account balance and exposure summary."""

    cash_balance: float
    total_value: float
    buying_power: float
    positions: list[Position] = field(default_factory=list)
    daily_pnl: float = 0.0


class BrokerInterface(ABC):
    """Abstract broker interface. Implement for mock or live broker."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the broker."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the broker connection."""

    @abstractmethod
    async def get_quote(self, ticker: str) -> Quote:
        """Get current quote for a symbol."""

    @abstractmethod
    async def get_order_book(self, ticker: str) -> OrderBook:
        """Get Level-2 order book for a symbol."""

    @abstractmethod
    async def submit_order(
        self,
        ticker: str,
        side: OrderSide,
        quantity: int,
        order_type: OrderType = OrderType.LIMIT,
        limit_price: float | None = None,
    ) -> OrderResult:
        """Submit an order. Returns an OrderResult with fill details."""

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order. Returns True if successful."""

    @abstractmethod
    async def get_positions(self) -> list[Position]:
        """Get all current open positions."""

    @abstractmethod
    async def get_account_summary(self) -> AccountSummary:
        """Get account balance and exposure summary."""

    @abstractmethod
    async def get_universe(self, max_price: float, min_price: float, min_volume: int) -> list[str]:
        """Get list of tickers matching universe filter criteria."""

    @abstractmethod
    async def subscribe_market_data(self, tickers: list[str]) -> None:
        """Subscribe to real-time market data for the given tickers."""

    @abstractmethod
    async def unsubscribe_market_data(self, tickers: list[str]) -> None:
        """Unsubscribe from market data for the given tickers."""
