from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.engine.l2_promotion_queue import L2PromotionQueue
from app.engine.l2_subscription_manager import L2SubscriptionManager
from app.engine.secret_sauce_handoff import SecretSauceHandoff


def _handoff(ticker: str, score: float) -> SecretSauceHandoff:
    return SecretSauceHandoff(
        ticker=ticker,
        score=score,
        detected_at=datetime.now(tz=timezone.utc),
        price_velocity_1m=4.0,
        volume_expansion=2.0,
        spread_pct=0.004,
        quote_rate=1.0,
        buy_pressure=0.7,
        reason_flags=["price_velocity"],
    )


@pytest.fixture
def broker():
    broker = AsyncMock()
    broker.subscribe_l2_depth = AsyncMock()
    broker.unsubscribe_l2_depth = AsyncMock()
    return broker


@pytest.mark.asyncio
async def test_promotion_queue_enqueues_by_score_and_drains_to_capacity(broker):
    manager = L2SubscriptionManager(broker, timeout_seconds=30.0)
    queue = L2PromotionQueue(manager, max_active=2, max_queue_size=10)

    added = queue.enqueue([
        _handoff("AAPL", 0.70),
        _handoff("TSLA", 0.90),
        _handoff("LCID", 0.80),
    ])
    promoted = await queue.drain_once()

    assert added == 3
    assert promoted == ["TSLA", "LCID"]
    assert queue.snapshot()["queued_tickers"] == ["AAPL"]


@pytest.mark.asyncio
async def test_promotion_queue_deduplicates_active_and_queued_symbols(broker):
    manager = L2SubscriptionManager(broker, timeout_seconds=30.0)
    queue = L2PromotionQueue(manager, max_active=3, max_queue_size=10)

    queue.enqueue([_handoff("AAPL", 0.8)])
    await queue.drain_once()
    added = queue.enqueue([_handoff("AAPL", 0.9), _handoff("AAPL", 0.85)])

    assert added == 0
    assert queue.snapshot()["active_tickers"] == ["AAPL"]


@pytest.mark.asyncio
async def test_promotion_queue_removes_excess_when_over_max_queue_size(broker):
    manager = L2SubscriptionManager(broker, timeout_seconds=30.0)
    queue = L2PromotionQueue(manager, max_active=1, max_queue_size=2)

    queue.enqueue([
        _handoff("AAPL", 0.7),
        _handoff("TSLA", 0.9),
        _handoff("LCID", 0.8),
    ])

    snapshot = queue.snapshot()
    assert snapshot["queued_tickers"] == ["TSLA", "LCID"]


@pytest.mark.asyncio
async def test_promotion_queue_rotates_out_weakest_replaceable_active(broker):
    manager = L2SubscriptionManager(broker, timeout_seconds=30.0)
    queue = L2PromotionQueue(manager, max_active=2, max_queue_size=10)

    queue.enqueue([
        _handoff("AAPL", 0.70),
        _handoff("TSLA", 0.75),
    ])
    await queue.drain_once()

    queue.enqueue([_handoff("LCID", 0.95)])
    promoted = await queue.drain_once()

    assert promoted == ["LCID"]
    broker.unsubscribe_l2_depth.assert_awaited_once_with("AAPL")
    assert queue.snapshot()["active_tickers"] == ["LCID", "TSLA"]


@pytest.mark.asyncio
async def test_promotion_queue_does_not_rotate_confirmed_slot(broker):
    manager = L2SubscriptionManager(broker, timeout_seconds=30.0)
    queue = L2PromotionQueue(manager, max_active=1, max_queue_size=10)

    queue.enqueue([_handoff("AAPL", 0.70)])
    await queue.drain_once()
    manager.mark_confirmed("AAPL")
    queue.mark_confirmed("AAPL")

    queue.enqueue([_handoff("TSLA", 0.95)])
    promoted = await queue.drain_once()

    assert promoted == []
    assert queue.snapshot()["queued_tickers"] == ["TSLA"]
    broker.unsubscribe_l2_depth.assert_not_awaited()


@pytest.mark.asyncio
async def test_promotion_queue_prunes_invalidated_active_slots(broker):
    manager = L2SubscriptionManager(broker, timeout_seconds=30.0)
    queue = L2PromotionQueue(manager, max_active=1, max_queue_size=10)

    queue.enqueue([_handoff("AAPL", 0.70)])
    await queue.drain_once()
    await manager.unsubscribe("AAPL")

    removed = queue.drop_stale_or_invalidated()

    assert removed == ["AAPL"]
    assert queue.snapshot()["active_tickers"] == []
