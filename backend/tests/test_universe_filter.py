"""Tests for the UniverseFilterEngine."""

from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from app.broker.interface import Quote
from app.broker.mock_broker import MockBroker
from app.engine.universe_filter import UniverseFilterEngine
from app.models.universe_daily import (
    UNIVERSE_KIND_MARKET,
    UNIVERSE_KIND_OPERATIONAL,
    UNIVERSE_SOURCE_ACTIVE_WATCHLIST,
    UNIVERSE_SOURCE_BROKER_FILTER,
    UniverseDaily,
)
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
    daily_rows = db.query(UniverseDaily).all()
    assert len(daily_rows) == len(tickers)
    assert all(row.universe_kind == UNIVERSE_KIND_OPERATIONAL for row in daily_rows)
    assert all(row.source == UNIVERSE_SOURCE_ACTIVE_WATCHLIST for row in daily_rows)


@pytest.mark.asyncio
async def test_get_active_tickers(broker, db: Session):
    engine = UniverseFilterEngine(broker, db)
    await engine.refresh_universe()
    active = engine.get_active_tickers()
    assert len(active) > 0
    assert all(isinstance(t, str) for t in active)


@pytest.mark.asyncio
async def test_get_secret_ingredients_tickers_reads_latest_persisted_snapshot(broker, db: Session):
    engine = UniverseFilterEngine(broker, db)
    await engine.refresh_secret_ingredients_universe()

    secret_tickers = engine.get_secret_ingredients_tickers()

    assert len(secret_tickers) > 0
    assert all(isinstance(t, str) for t in secret_tickers)


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


@pytest.mark.asyncio
async def test_refresh_secret_ingredients_universe_persists_daily_snapshot_without_owning_active_flags(
    broker, db: Session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr("app.engine.universe_filter.settings.secret_universe_excluded_tickers", "AAPL")

    db.add(Symbol(ticker="AAPL", name="Apple", exchange="NASDAQ", is_active=True))
    db.commit()

    engine = UniverseFilterEngine(broker, db)
    tickers = await engine.refresh_secret_ingredients_universe()

    assert "AAPL" not in tickers
    assert len(tickers) > 0

    daily_rows = db.query(UniverseDaily).all()
    assert len(daily_rows) == len(tickers)
    assert {row.ticker for row in daily_rows} == set(tickers)
    assert all(row.universe_kind == UNIVERSE_KIND_MARKET for row in daily_rows)
    assert all(row.source == UNIVERSE_SOURCE_BROKER_FILTER for row in daily_rows)

    aapl = db.query(Symbol).filter_by(ticker="AAPL").first()
    assert aapl is not None
    assert aapl.is_active is True


@pytest.mark.asyncio
async def test_refresh_secret_ingredients_universe_uses_supplied_quotes_without_broker_fetch(
    broker, db: Session
):
    async def _boom(_ticker):
        raise AssertionError("broker.get_quote should not be called when universe_quotes are supplied")

    broker.get_quote = _boom
    engine = UniverseFilterEngine(broker, db)

    tickers = await engine.refresh_secret_ingredients_universe(
        universe_quotes=[
            Quote(
                ticker="LCID",
                bid=3.4,
                ask=3.5,
                last=3.45,
                volume=250000,
                timestamp=datetime.now(),
            )
        ]
    )

    assert tickers == ["LCID"]
    lcid = db.query(Symbol).filter_by(ticker="LCID").first()
    assert lcid is not None
    assert lcid.last_price == 3.45
    assert lcid.avg_volume == 250000
