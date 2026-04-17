from datetime import datetime

from app.broker.interface import Quote
from app.data.polygon_tick_persister import PolygonTickPersister
from app.models.polygon_tick import PolygonTick
from app.models.polygon_tick_live import PolygonTickLive


def test_polygon_tick_persister_skips_exact_duplicate_quotes(db_session_factory):
    persister = PolygonTickPersister(db_session_factory, batch_size=10)
    quote = Quote(
        ticker="DVLT",
        bid=0.828,
        ask=0.83,
        last=0.829,
        volume=3,
        timestamp=datetime(2026, 4, 16, 19, 42, 40, 302000),
        event_type="quote",
    )

    persister.record(quote)
    persister.record(quote)
    persister.flush()

    db = db_session_factory()
    assert db.query(PolygonTick).count() == 1
    assert db.query(PolygonTickLive).count() == 1
    db.close()


def test_polygon_tick_persister_persists_distinct_quotes(db_session_factory):
    persister = PolygonTickPersister(db_session_factory, batch_size=10)

    persister.record(
        Quote(
            ticker="DVLT",
            bid=0.828,
            ask=0.83,
            last=0.829,
            volume=3,
            timestamp=datetime(2026, 4, 16, 19, 42, 40, 302000),
            event_type="quote",
        )
    )
    persister.record(
        Quote(
            ticker="DVLT",
            bid=0.8276,
            ask=0.83,
            last=0.8288,
            volume=3,
            timestamp=datetime(2026, 4, 16, 19, 42, 40, 302000),
            event_type="quote",
        )
    )
    persister.flush()

    db = db_session_factory()
    assert db.query(PolygonTick).count() == 2
    assert db.query(PolygonTickLive).count() == 2
    db.close()
