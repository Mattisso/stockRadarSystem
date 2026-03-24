"""Tests for the Polygon breakout queue consumer."""

import asyncio
from datetime import datetime

import pytest

from app.broker.interface import Quote
from app.engine.breakout_engine import BreakoutEngine
from app.data.polygon_queue_consumer import BreakoutQueueConsumer


@pytest.mark.asyncio
async def test_breakout_queue_consumer_ingests_quotes():
    queue: asyncio.Queue[Quote] = asyncio.Queue()
    engine = BreakoutEngine()
    consumer = BreakoutQueueConsumer(queue, engine)

    await consumer.start()
    await queue.put(Quote(ticker="AAPL", bid=1.0, ask=1.1, last=1.05, volume=100, timestamp=datetime.now()))
    await queue.join()
    await consumer.stop()

    assert engine.active_trackers == 1
    assert len(engine.get_tracker("AAPL").ticks) == 1
