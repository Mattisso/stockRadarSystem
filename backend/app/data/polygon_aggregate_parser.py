"""Polygon WebSocket aggregate message parsing."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class AggregateBar:
    ticker: str
    event_type: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: float | None = None
    transactions: int | None = None


class PolygonAggregateParser:
    """Parse Polygon aggregate websocket payloads for A / AM events."""

    def parse_message(self, msg: dict[str, Any]) -> AggregateBar | None:
        if not isinstance(msg, dict):
            return None
        event_type = msg.get("ev")
        if event_type not in {"A", "AM"}:
            return None

        ticker = msg.get("sym")
        timestamp_raw = msg.get("s", msg.get("t"))
        if not ticker or timestamp_raw is None:
            return None

        try:
            timestamp = datetime.fromtimestamp(float(timestamp_raw) / 1000, tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            return None

        try:
            open_price = float(msg.get("o"))
            high_price = float(msg.get("h"))
            low_price = float(msg.get("l"))
            close_price = float(msg.get("c"))
            volume = int(float(msg.get("v", 0)))
        except (TypeError, ValueError):
            return None

        vwap = self._parse_optional_float(msg.get("vw"))
        transactions = self._parse_optional_int(msg.get("n"))

        return AggregateBar(
            ticker=str(ticker).upper(),
            event_type=event_type,
            timestamp=timestamp,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
            vwap=vwap,
            transactions=transactions,
        )

    def parse_messages(self, payload: str | bytes | dict[str, Any] | list[dict[str, Any]]) -> list[AggregateBar]:
        if isinstance(payload, (str, bytes)):
            decoded = json.loads(payload)
        else:
            decoded = payload

        if isinstance(decoded, list):
            raw_messages = [msg for msg in decoded if isinstance(msg, dict)]
        elif isinstance(decoded, dict):
            raw_messages = [decoded]
        else:
            return []

        bars: list[AggregateBar] = []
        for msg in raw_messages:
            bar = self.parse_message(msg)
            if bar is not None:
                bars.append(bar)
        return bars

    @staticmethod
    def _parse_optional_float(value: Any) -> float | None:
        if value in ("", None):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_optional_int(value: Any) -> int | None:
        if value in ("", None):
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

