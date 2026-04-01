from datetime import datetime, timedelta, timezone

from app.broker.interface import Quote
from app.data.cache import InMemoryCache
from app.engine.l1_feature_engine import L1FeatureEngine


def _quote(
    ticker: str,
    *,
    bid: float,
    ask: float,
    last: float,
    volume: int,
    timestamp: datetime,
) -> Quote:
    return Quote(
        ticker=ticker,
        bid=bid,
        ask=ask,
        last=last,
        volume=volume,
        timestamp=timestamp,
    )


def test_l1_feature_engine_computes_snapshot():
    engine = L1FeatureEngine()
    start = datetime(2026, 3, 31, 12, 0, 0, tzinfo=timezone.utc)

    for idx in range(10):
        engine.ingest(
            _quote(
                "AAPL",
                bid=10.0 + idx * 0.05,
                ask=10.1 + idx * 0.04,
                last=10.05 + idx * 0.05,
                volume=100 + idx * 20,
                timestamp=start + timedelta(seconds=idx * 5),
            )
        )

    snapshot = engine.snapshot("AAPL")

    assert snapshot is not None
    assert snapshot.price_velocity_1m > 0
    assert snapshot.spread_pct > 0
    assert snapshot.quote_rate > 0
    assert snapshot.volume_expansion > 0
    assert snapshot.buy_pressure > 0


def test_buy_pressure_strengthens_with_bid_lift_and_spread_compression():
    engine = L1FeatureEngine()
    start = datetime(2026, 3, 31, 12, 0, 0, tzinfo=timezone.utc)

    for idx in range(6):
        engine.ingest(
            _quote(
                "LCID",
                bid=3.00 + idx * 0.01,
                ask=3.08 + idx * 0.005,
                last=3.04 + idx * 0.008,
                volume=1_000 + idx * 100,
                timestamp=start + timedelta(seconds=idx * 5),
            )
        )

    snapshot = engine.snapshot("LCID")
    assert snapshot is not None
    assert snapshot.buy_pressure >= 0.6


async def test_ingest_from_cache_reads_existing_quotes():
    cache = InMemoryCache(ttl=10)
    await cache.connect()
    engine = L1FeatureEngine()
    quote = _quote(
        "TSLA",
        bid=5.0,
        ask=5.1,
        last=5.05,
        volume=500,
        timestamp=datetime.now(tz=timezone.utc),
    )
    await cache.set_l1("TSLA", quote)

    await engine.ingest_from_cache(cache, ["TSLA"])

    snapshot = engine.snapshot("TSLA")
    assert snapshot is not None
    assert snapshot.last_price == 5.05
