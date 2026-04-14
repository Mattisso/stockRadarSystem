from datetime import datetime, timezone

from app.data.polygon_aggregate_parser import PolygonAggregateParser


def test_parse_second_aggregate_message():
    parser = PolygonAggregateParser()

    bar = parser.parse_message(
        {
            "ev": "A",
            "sym": "LCID",
            "o": 3.1,
            "h": 3.2,
            "l": 3.0,
            "c": 3.15,
            "v": 500,
            "vw": 3.12,
            "n": 8,
            "s": 1712946601000,
        }
    )

    assert bar is not None
    assert bar.event_type == "A"
    assert bar.ticker == "LCID"
    assert bar.timestamp == datetime.fromtimestamp(1712946601, tz=timezone.utc)
    assert bar.close == 3.15


def test_parse_minute_aggregate_message():
    parser = PolygonAggregateParser()

    bar = parser.parse_message(
        {
            "ev": "AM",
            "sym": "LCID",
            "o": 3.1,
            "h": 3.2,
            "l": 3.0,
            "c": 3.15,
            "v": 5000,
            "vw": 3.12,
            "n": 40,
            "s": 1712946660000,
        }
    )

    assert bar is not None
    assert bar.event_type == "AM"
    assert bar.ticker == "LCID"
    assert bar.volume == 5000

