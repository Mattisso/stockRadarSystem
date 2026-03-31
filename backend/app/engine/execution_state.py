"""Execution lifecycle state tracked outside the broker registry."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ExecutionPhase(str, Enum):
    ENTRY_FILLED = "entry_filled"
    MANAGED = "managed"
    RUNNER_MODE = "runner_mode"
    EXIT_PENDING = "exit_pending"
    CLOSED = "closed"


@dataclass
class ManagedExecutionState:
    """Executor-side lifecycle state for an open or recently closed trade."""

    ticker: str
    trade_id: int
    order_id: str
    filled_at: datetime
    target_order_id: str | None = None
    stop_order_id: str | None = None
    current_stop_price: float | None = None
    phase: ExecutionPhase = ExecutionPhase.ENTRY_FILLED
    runner_mode_started_at: datetime | None = None
    last_reason: str | None = None
    last_updated_at: datetime = field(default_factory=datetime.now)

    def mark_managed(self) -> None:
        self.phase = ExecutionPhase.MANAGED
        self.last_updated_at = datetime.now()

    def mark_runner_mode(self) -> None:
        self.phase = ExecutionPhase.RUNNER_MODE
        self.runner_mode_started_at = datetime.now()
        self.last_updated_at = datetime.now()

    def mark_exit_pending(self, reason: str | None) -> None:
        self.phase = ExecutionPhase.EXIT_PENDING
        self.last_reason = reason
        self.last_updated_at = datetime.now()

    def mark_closed(self, reason: str | None) -> None:
        self.phase = ExecutionPhase.CLOSED
        self.last_reason = reason
        self.last_updated_at = datetime.now()

    def update_stop_price(self, stop_price: float) -> None:
        self.current_stop_price = stop_price
        self.last_updated_at = datetime.now()
