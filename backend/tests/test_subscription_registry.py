"""Tests for the Polygon subscription registry."""

from app.data.subscription_registry import SubscriptionRegistry


def test_subscription_registry_dedupes_and_preserves_source_order():
    registry = SubscriptionRegistry(initial_sources={"watchlist": ["aapl", "TSLA", "AAPL"]})

    changed = registry.update_source("secret_universe", ["LCID", "AAPL", "gevo"])

    assert changed is True
    assert registry.current_symbols() == ["AAPL", "TSLA", "LCID", "GEVO"]
    assert registry.generation_id == 1


def test_subscription_registry_tracks_sticky_sources_without_false_generation_bumps():
    registry = SubscriptionRegistry(initial_sources={"watchlist": ["AAPL"]})

    assert registry.update_source("watchlist", ["AAPL"]) is False
    assert registry.generation_id == 0

    assert registry.update_source("operational", ["LCID", "AAPL"], sticky=True) is True
    assert registry.current_symbols() == ["AAPL", "LCID"]
    assert registry.sticky_symbols() == ["LCID", "AAPL"]
    assert registry.generation_id == 1

    assert registry.update_source("operational", ["LCID", "AAPL"], sticky=True) is False
    assert registry.generation_id == 1

    source_states = registry.source_states()
    assert source_states[0].source == "watchlist"
    assert source_states[0].sticky is False
    assert source_states[1].source == "operational"
    assert source_states[1].sticky is True
