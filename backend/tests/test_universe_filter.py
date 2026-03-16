"""Tests for the UniverseFilterEngine."""

import pytest
from sqlalchemy.orm import Session

from app.broker.mock_broker import MockBroker
from app.engine.universe_filter import UniverseFilterEngine
from app.models.symbol import Symbol


@pytest.fixture
async def broker():
    b = MockBroker()
    await b.connect()
    yield b
    await b.disconnect()


@pytest.mark.asyncio
async def test_refresh_universe(broker, db: Session):
    engine = UniverseFilterEngine(broker, db)
    tickers = await engine.refresh_universe()
    assert len(tickers) > 0

    # Verify symbols are in the database
    symbols = db.query(Symbol).filter_by(is_active=True).all()
    assert len(symbols) == len(tickers)


@pytest.mark.asyncio
async def test_get_active_tickers(broker, db: Session):
    engine = UniverseFilterEngine(broker, db)
    await engine.refresh_universe()
    active = engine.get_active_tickers()
    assert len(active) > 0
    assert all(isinstance(t, str) for t in active)


@pytest.mark.asyncio
async def test_refresh_deactivates_removed_symbols(broker, db: Session):
    # Pre-populate a symbol that won't be in the mock universe
    db.add(Symbol(ticker="FAKE", name="Fake Co", exchange="NASDAQ", is_active=True))
    db.commit()

    engine = UniverseFilterEngine(broker, db)
    await engine.refresh_universe()

    fake = db.query(Symbol).filter_by(ticker="FAKE").first()
    assert fake is not None
    assert fake.is_active is False
