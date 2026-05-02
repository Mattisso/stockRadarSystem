from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


AggregateEventType = Literal["A", "AM"]


@dataclass(slots=True)
class PolygonAggregateEvent:
    ticker: str
    event_type: AggregateEventType
    event_ts: datetime
    received_at: datetime
    subscription_generation_id: int
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: float | None = None
    transactions: int | None = None
