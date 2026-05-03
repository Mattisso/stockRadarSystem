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

    def to_payload(self) -> dict[str, str]:
        return {
            "ticker": self.ticker,
            "event_type": self.event_type,
            "event_ts": self.event_ts.isoformat(),
            "received_at": self.received_at.isoformat(),
            "subscription_generation_id": str(self.subscription_generation_id),
            "open": str(self.open),
            "high": str(self.high),
            "low": str(self.low),
            "close": str(self.close),
            "volume": str(self.volume),
            "vwap": "" if self.vwap is None else str(self.vwap),
            "transactions": "" if self.transactions is None else str(self.transactions),
        }

    @classmethod
    def from_payload(cls, payload: dict[str, str]) -> "PolygonAggregateEvent":
        return cls(
            ticker=payload["ticker"],
            event_type=payload["event_type"],  # type: ignore[arg-type]
            event_ts=datetime.fromisoformat(payload["event_ts"]),
            received_at=datetime.fromisoformat(payload["received_at"]),
            subscription_generation_id=int(payload["subscription_generation_id"]),
            open=float(payload["open"]),
            high=float(payload["high"]),
            low=float(payload["low"]),
            close=float(payload["close"]),
            volume=int(payload["volume"]),
            vwap=float(payload["vwap"]) if payload.get("vwap") not in {None, ""} else None,
            transactions=(
                int(payload["transactions"])
                if payload.get("transactions") not in {None, ""}
                else None
            ),
        )
