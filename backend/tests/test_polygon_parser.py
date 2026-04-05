"""Tests for Polygon message parsing."""

import json
from datetime import datetime, timezone

from app.data.polygon_parser import PolygonMessageParser


def test_parse_quote_message():
    parser = PolygonMessageParser()
    timestamp_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)

    quote = parser.parse_message({
        "ev": "Q",
        "sym": "AAPL",
        "bp": 150.25,
        "ap": 150.3,
        "z": 12345,
        "t": timestamp_ms,
    })

    assert quote is not None
    assert quote.ticker == "AAPL"
    assert quote.bid == 150.25
    assert quote.ask == 150.3
    assert quote.last == 150.275
    assert quote.volume == 12345
    assert quote.timestamp == datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
    assert quote.event_type == "quote"


def test_parse_quote_message_falls_back_when_only_one_side_present():
    parser = PolygonMessageParser()
    timestamp_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)

    quote = parser.parse_message({
        "ev": "Q",
        "sym": "AAPL",
        "bp": 150.25,
        "ap": 0.0,
        "z": 10,
        "t": timestamp_ms,
    })

    assert quote is not None
    assert quote.last == 150.25


def test_parse_non_quote_message_returns_none():
    parser = PolygonMessageParser()
    assert parser.parse_message({"ev": "status", "message": "connected"}) is None


def test_parse_trade_message():
    parser = PolygonMessageParser()
    timestamp_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)

    trade = parser.parse_message({
        "ev": "T",
        "sym": "AAPL",
        "p": 150.55,
        "s": 2500,
        "t": timestamp_ms,
    })

    assert trade is not None
    assert trade.ticker == "AAPL"
    assert trade.last == 150.55
    assert trade.volume == 2500
    assert trade.event_type == "trade"


def test_parse_messages_handles_json_batches():
    parser = PolygonMessageParser()
    timestamp_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)

    quotes = parser.parse_messages(json.dumps([
        {"ev": "status", "message": "connected"},
        {"ev": "Q", "sym": "AAPL", "bp": 150.25, "ap": 150.3, "z": 12345, "t": timestamp_ms},
        {"ev": "T", "sym": "AAPL", "p": 150.4, "s": 1000, "t": timestamp_ms},
    ]))

    assert len(quotes) == 2
    assert quotes[0].ticker == "AAPL"
    assert quotes[0].event_type == "quote"
    assert quotes[1].event_type == "trade"
