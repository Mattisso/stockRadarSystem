"""Polygon WebSocket message parsing."""

import json
from datetime import datetime, timezone
from typing import Any

from app.broker.interface import Quote


class PolygonMessageParser:
    """Parse Polygon quote and trade payloads into internal Quote objects."""

    def parse_message(self, msg: dict[str, Any]) -> Quote | None:
        """Parse a single Polygon message.

        Quote messages (`ev == "Q"`) and trade messages (`ev == "T"`) are converted.
        Unsupported or malformed messages are ignored.
        """
        if not isinstance(msg, dict):
            return None

        timestamp = msg.get("t")
        if timestamp is None:
            return None

        event_type = msg.get("ev")
        if event_type == "Q":
            return Quote(
                ticker=msg.get("sym", ""),
                bid=msg.get("bp", 0.0),
                ask=msg.get("ap", 0.0),
                last=msg.get("bp", 0.0),
                volume=msg.get("z", 0),
                timestamp=datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc),
                event_type="quote",
            )
        if event_type == "T":
            price = msg.get("p", 0.0)
            size = msg.get("s", 0)
            return Quote(
                ticker=msg.get("sym", ""),
                bid=price,
                ask=price,
                last=price,
                volume=size,
                timestamp=datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc),
                event_type="trade",
            )

        return None

    def parse_messages(self, payload: str | bytes | dict[str, Any] | list[dict[str, Any]]) -> list[Quote]:
        """Parse a WebSocket payload into zero or more Quote objects."""
        raw_messages: list[dict[str, Any]]
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

        quotes: list[Quote] = []
        for msg in raw_messages:
            quote = self.parse_message(msg)
            if quote is not None:
                quotes.append(quote)
        return quotes
