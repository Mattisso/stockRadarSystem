"""In-memory tracking for active IBKR bracket order chains."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class OrderChainState:
    ticker: str
    parent_order_id: str
    target_order_id: str
    stop_order_id: str
    parent_side: str
    entry_order_type: str
    quantity: int
    target_price: float
    stop_price: float
    fill_price: float | None = None
    filled_quantity: int = 0
    status: str = "submitted"
    runner_mode: bool = False
    submitted_at: datetime = field(default_factory=datetime.now)
    filled_at: datetime | None = None
    last_stop_update_at: datetime | None = None


class OrderRegistry:
    """Tracks working order chains by parent order id."""

    def __init__(self) -> None:
        self._chains: dict[str, OrderChainState] = {}

    def register(self, chain: OrderChainState) -> None:
        self._chains[chain.parent_order_id] = chain

    def get(self, parent_order_id: str) -> OrderChainState | None:
        return self._chains.get(parent_order_id)

    def remove(self, parent_order_id: str) -> None:
        self._chains.pop(parent_order_id, None)

    def by_child_order_id(self, order_id: str) -> OrderChainState | None:
        for chain in self._chains.values():
            if order_id in {chain.parent_order_id, chain.target_order_id, chain.stop_order_id}:
                return chain
        return None

    def update_fill(
        self,
        parent_order_id: str,
        *,
        fill_price: float | None,
        filled_quantity: int,
        status: str,
    ) -> None:
        chain = self._chains.get(parent_order_id)
        if chain is None:
            return
        chain.fill_price = fill_price
        chain.filled_quantity = filled_quantity
        chain.status = status
        if filled_quantity > 0 and chain.filled_at is None:
            chain.filled_at = datetime.now()

    def update_stop(self, parent_order_id: str, new_stop_price: float) -> bool:
        chain = self._chains.get(parent_order_id)
        if chain is None:
            return False
        if new_stop_price < chain.stop_price:
            return False
        chain.stop_price = new_stop_price
        chain.last_stop_update_at = datetime.now()
        return True

    def mark_runner_mode(self, parent_order_id: str) -> None:
        chain = self._chains.get(parent_order_id)
        if chain is not None:
            chain.runner_mode = True
