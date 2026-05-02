"""Tests for PolygonAggregateEvent dataclass."""

from datetime import datetime, timezone

from app.data.polygon_event_models import PolygonAggregateEvent


def test_aggregate_event_required_fields():
    now = datetime.now(tz=timezone.utc)
    event = PolygonAggregateEvent(
        ticker="LCID",
        event_type="A",
        event_ts=now,
        received_at=now,
        subscription_generation_id=42,
        open=3.10,
        high=3.15,
        low=3.09,
        close=3.12,
        volume=500,
    )

    assert event.ticker == "LCID"
    assert event.event_type == "A"
    assert event.event_ts == now
    assert event.received_at == now
    assert event.subscription_generation_id == 42
    assert event.open == 3.10
    assert event.high == 3.15
    assert event.low == 3.09
    assert event.close == 3.12
    assert event.volume == 500
    assert event.vwap is None
    assert event.transactions is None


def test_aggregate_event_optional_fields():
    now = datetime.now(tz=timezone.utc)
    event = PolygonAggregateEvent(
        ticker="GEVO",
        event_type="AM",
        event_ts=now,
        received_at=now,
        subscription_generation_id=7,
        open=1.50,
        high=1.55,
        low=1.49,
        close=1.53,
        volume=12000,
        vwap=1.52,
        transactions=88,
    )

    assert event.vwap == 1.52
    assert event.transactions == 88


def test_aggregate_event_uses_slots():
    assert hasattr(PolygonAggregateEvent, "__slots__")

    now = datetime.now(tz=timezone.utc)
    event = PolygonAggregateEvent(
        ticker="AAPL",
        event_type="A",
        event_ts=now,
        received_at=now,
        subscription_generation_id=1,
        open=1.0,
        high=1.0,
        low=1.0,
        close=1.0,
        volume=1,
    )
    assert not hasattr(event, "__dict__")


def test_aggregate_event_equality():
    now = datetime.now(tz=timezone.utc)
    kwargs = dict(
        ticker="LCID",
        event_type="A",
        event_ts=now,
        received_at=now,
        subscription_generation_id=1,
        open=3.10,
        high=3.15,
        low=3.09,
        close=3.12,
        volume=500,
    )

    assert PolygonAggregateEvent(**kwargs) == PolygonAggregateEvent(**kwargs)


def test_aggregate_event_type_accepts_a_and_am():
    now = datetime.now(tz=timezone.utc)
    base = dict(
        ticker="X",
        event_ts=now,
        received_at=now,
        subscription_generation_id=1,
        open=1.0,
        high=1.0,
        low=1.0,
        close=1.0,
        volume=1,
    )

    second = PolygonAggregateEvent(event_type="A", **base)
    minute = PolygonAggregateEvent(event_type="AM", **base)

    assert second.event_type == "A"
    assert minute.event_type == "AM"
