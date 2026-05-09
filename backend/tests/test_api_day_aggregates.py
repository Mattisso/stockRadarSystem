from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.api.routes import get_db
from app.main import app
from app.models.polygon_day_aggregate import PolygonDayAggregate
from app.models.universe_daily import UniverseDaily


def test_polygon_day_aggregates_reads_latest_trade_date_rows(db_engine, auth_headers):
    TestingSessionLocal = sessionmaker(bind=db_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestingSessionLocal() as db:
            db.add_all(
                [
                    UniverseDaily(
                        trade_date=date(2026, 4, 11),
                        ticker="ALTS",
                        open_price=1.12,
                        last_price=1.10,
                        avg_volume=1_100_000,
                    ),
                    UniverseDaily(
                        trade_date=date(2026, 4, 10),
                        ticker="OLDR",
                        open_price=1.12,
                        last_price=1.10,
                        avg_volume=1_100_000,
                    ),
                    PolygonDayAggregate(
                        trade_date=date(2026, 4, 10),
                        ticker="OLDR",
                        open=1.0,
                        high=1.1,
                        low=0.9,
                        close=1.05,
                        volume=500,
                        vwap=1.02,
                        transactions=5,
                    ),
                    PolygonDayAggregate(
                        trade_date=date(2026, 4, 11),
                        ticker="ALTS",
                        open=1.1,
                        high=1.2,
                        low=1.0,
                        close=1.15,
                        volume=900,
                        vwap=1.12,
                        transactions=9,
                    ),
                    PolygonDayAggregate(
                        trade_date=date(2026, 4, 11),
                        ticker="AAPL",
                        open=150.0,
                        high=151.0,
                        low=149.5,
                        close=150.5,
                        volume=9_000_000,
                        vwap=150.2,
                        transactions=900,
                    ),
                ]
            )
            db.commit()

        with TestClient(app) as client:
            response = client.get(
                "/api/polygon/day-aggregates",
                headers=auth_headers,
                params={"page": 0, "page_size": 10},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["trade_date"] == "2026-04-11"
        assert body["total"] == 1
        assert len(body["items"]) == 1
        assert body["items"][0]["ticker"] == "ALTS"
        assert body["items"][0]["close"] == 1.15
    finally:
        app.dependency_overrides.pop(get_db, None)
