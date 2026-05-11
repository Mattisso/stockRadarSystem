from datetime import date, datetime, timedelta

from app.engine.secret_ingredients import SecretIngredientsService
from app.models.universe_daily import (
    UNIVERSE_KIND_MARKET,
    UNIVERSE_KIND_OPERATIONAL,
    UNIVERSE_SOURCE_ACTIVE_WATCHLIST,
    UNIVERSE_SOURCE_POLYGON_FLATFILE,
    UniverseDaily,
)
from app.models.symbol_state_live import SymbolStateLive
from app.models.trade import Trade, TradeSide, TradeStatus


def test_select_aggregate_subscription_tickers_uses_aggregate_defaults(monkeypatch):
    class FakeQuery:
        def __init__(self, value):
            self._value = value

        def order_by(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def scalar(self):
            return self._value

        def outerjoin(self, *_args, **_kwargs):
            return self

        def filter(self, *_args, **_kwargs):
            return self

        def all(self):
            return [
                (type("U", (), {"ticker": "WLDS", "avg_volume": 123, "last_price": 2.5})(), None),
            ]

    class FakeDb:
        def __init__(self):
            self.calls = 0

        def query(self, *_args, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return FakeQuery("2026-04-21")
            return FakeQuery(None)

    service = SecretIngredientsService(db=FakeDb())
    monkeypatch.setattr("app.engine.secret_ingredients.settings.aggregate_live_max_symbols", 0)
    monkeypatch.setattr("app.engine.secret_ingredients.settings.aggregate_live_min_avg_volume", 0)

    tickers = service.select_aggregate_subscription_tickers()

    assert tickers == ["WLDS"]


def test_select_aggregate_subscription_tickers_returns_full_ranked_set_when_uncapped(monkeypatch):
    class FakeQuery:
        def __init__(self, value):
            self._value = value

        def order_by(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def scalar(self):
            return self._value

        def outerjoin(self, *_args, **_kwargs):
            return self

        def filter(self, *_args, **_kwargs):
            return self

        def all(self):
            return [
                (type("U", (), {"ticker": "AAA", "avg_volume": 10, "last_price": 1.0})(), None),
                (type("U", (), {"ticker": "BBB", "avg_volume": 20, "last_price": 2.0})(), None),
            ]

    class FakeDb:
        def __init__(self):
            self.calls = 0

        def query(self, *_args, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return FakeQuery("2026-04-21")
            return FakeQuery(None)

    service = SecretIngredientsService(db=FakeDb())
    monkeypatch.setattr("app.engine.secret_ingredients.settings.aggregate_live_max_symbols", 0)
    monkeypatch.setattr("app.engine.secret_ingredients.settings.aggregate_live_min_avg_volume", 0)

    tickers = service.select_aggregate_subscription_tickers()

    assert tickers == ["BBB", "AAA"]


def test_select_operational_subscription_tickers_prioritizes_open_trades_and_active_states(
    db,
    monkeypatch,
):
    now = datetime(2026, 5, 2, 14, 0, 0)
    monkeypatch.setattr("app.engine.secret_ingredients.settings.secret_universe_source", "polygon")
    monkeypatch.setattr(
        "app.engine.secret_ingredients.settings.polygon_operational_subscription_max_symbols",
        3,
    )
    monkeypatch.setattr(
        "app.engine.secret_ingredients.settings.polygon_operational_recent_sold_minutes",
        30,
    )

    db.add_all(
        [
            UniverseDaily(
                trade_date=date(2026, 5, 2),
                ticker="OPEN1",
                universe_kind=UNIVERSE_KIND_MARKET,
                source=UNIVERSE_SOURCE_POLYGON_FLATFILE,
            ),
            UniverseDaily(
                trade_date=date(2026, 5, 2),
                ticker="OPEN2",
                universe_kind=UNIVERSE_KIND_MARKET,
                source=UNIVERSE_SOURCE_POLYGON_FLATFILE,
            ),
            UniverseDaily(
                trade_date=date(2026, 5, 2),
                ticker="MANAGE1",
                universe_kind=UNIVERSE_KIND_MARKET,
                source=UNIVERSE_SOURCE_POLYGON_FLATFILE,
            ),
            UniverseDaily(
                trade_date=date(2026, 5, 2),
                ticker="CAND1",
                universe_kind=UNIVERSE_KIND_MARKET,
                source=UNIVERSE_SOURCE_POLYGON_FLATFILE,
            ),
            UniverseDaily(
                trade_date=date(2026, 5, 2),
                ticker="SOLD1",
                universe_kind=UNIVERSE_KIND_MARKET,
                source=UNIVERSE_SOURCE_POLYGON_FLATFILE,
            ),
        ]
    )
    db.add_all(
        [
            Trade(
                ticker="OPEN1",
                side=TradeSide.BUY,
                status=TradeStatus.FILLED,
                quantity=100,
                created_at=now - timedelta(minutes=2),
            ),
            Trade(
                ticker="OPEN2",
                side=TradeSide.BUY,
                status=TradeStatus.PENDING,
                quantity=100,
                created_at=now - timedelta(minutes=1),
            ),
            SymbolStateLive(
                ticker="MANAGE1",
                candidate_status="manage",
                updated_at=now - timedelta(minutes=3),
            ),
            SymbolStateLive(
                ticker="CAND1",
                candidate_status="candidate",
                updated_at=now - timedelta(minutes=4),
            ),
            SymbolStateLive(
                ticker="SOLD1",
                candidate_status="sold",
                updated_at=now - timedelta(minutes=10),
            ),
            SymbolStateLive(
                ticker="SOLD_OLD",
                candidate_status="sold",
                updated_at=now - timedelta(minutes=45),
            ),
        ]
    )
    db.commit()

    service = SecretIngredientsService(db)
    tickers = service.select_operational_subscription_tickers(now=now)

    assert tickers == ["OPEN2", "OPEN1", "MANAGE1"]


def test_select_operational_subscription_tickers_does_not_expand_beyond_market_universe(
    db,
    monkeypatch,
):
    now = datetime(2026, 5, 2, 14, 0, 0)
    monkeypatch.setattr("app.engine.secret_ingredients.settings.secret_universe_source", "polygon")
    monkeypatch.setattr(
        "app.engine.secret_ingredients.settings.polygon_operational_subscription_max_symbols",
        10,
    )
    monkeypatch.setattr(
        "app.engine.secret_ingredients.settings.polygon_operational_recent_sold_minutes",
        30,
    )

    db.add(
        UniverseDaily(
            trade_date=date(2026, 5, 2),
            ticker="IN_UNIVERSE",
            universe_kind=UNIVERSE_KIND_MARKET,
            source=UNIVERSE_SOURCE_POLYGON_FLATFILE,
        )
    )
    db.add_all(
        [
            Trade(
                ticker="OUTSIDE_TRADE",
                side=TradeSide.BUY,
                status=TradeStatus.FILLED,
                quantity=100,
                created_at=now - timedelta(minutes=1),
            ),
            SymbolStateLive(
                ticker="OUTSIDE_STATE",
                candidate_status="manage",
                updated_at=now - timedelta(minutes=2),
            ),
            SymbolStateLive(
                ticker="IN_UNIVERSE",
                candidate_status="candidate",
                updated_at=now - timedelta(minutes=3),
            ),
        ]
    )
    db.commit()

    service = SecretIngredientsService(db)
    tickers = service.select_operational_subscription_tickers(now=now)

    assert tickers == ["IN_UNIVERSE"]


def test_select_aggregate_subscription_tickers_ignores_newer_operational_snapshot(db, monkeypatch):
    db.add_all(
        [
            UniverseDaily(
                trade_date=date(2026, 5, 1),
                ticker="LCID",
                universe_kind=UNIVERSE_KIND_MARKET,
                source=UNIVERSE_SOURCE_POLYGON_FLATFILE,
                open_price=3.2,
                last_price=3.3,
                avg_volume=500_000,
            ),
            UniverseDaily(
                trade_date=date(2026, 5, 1),
                ticker="SOFI",
                universe_kind=UNIVERSE_KIND_MARKET,
                source=UNIVERSE_SOURCE_POLYGON_FLATFILE,
                open_price=6.0,
                last_price=6.1,
                avg_volume=900_000,
            ),
            UniverseDaily(
                trade_date=date(2026, 5, 4),
                ticker="LCID",
                universe_kind=UNIVERSE_KIND_OPERATIONAL,
                source=UNIVERSE_SOURCE_ACTIVE_WATCHLIST,
            ),
        ]
    )
    db.commit()

    monkeypatch.setattr("app.engine.secret_ingredients.settings.secret_universe_source", "polygon")
    monkeypatch.setattr("app.engine.secret_ingredients.settings.aggregate_live_max_symbols", 0)
    monkeypatch.setattr("app.engine.secret_ingredients.settings.aggregate_live_min_avg_volume", 0)

    tickers = SecretIngredientsService(db).select_aggregate_subscription_tickers()

    assert tickers == ["SOFI", "LCID"]


def test_record_daily_universe_replaces_stale_rows_for_same_trade_date_and_source(db):
    service = SecretIngredientsService(db)

    db.add_all(
        [
            UniverseDaily(
                trade_date=date(2026, 5, 8),
                ticker="AAA",
                universe_kind=UNIVERSE_KIND_MARKET,
                source=UNIVERSE_SOURCE_POLYGON_FLATFILE,
            ),
            UniverseDaily(
                trade_date=date(2026, 5, 8),
                ticker="BBB",
                universe_kind=UNIVERSE_KIND_MARKET,
                source=UNIVERSE_SOURCE_POLYGON_FLATFILE,
            ),
            UniverseDaily(
                trade_date=date(2026, 5, 8),
                ticker="CCC",
                universe_kind=UNIVERSE_KIND_MARKET,
                source=UNIVERSE_SOURCE_POLYGON_FLATFILE,
            ),
        ]
    )
    db.commit()

    service.record_daily_universe(
        ["AAA", "BBB"],
        trade_date=date(2026, 5, 8),
        universe_kind=UNIVERSE_KIND_MARKET,
        source=UNIVERSE_SOURCE_POLYGON_FLATFILE,
    )
    db.commit()

    rows = (
        db.query(UniverseDaily)
        .filter_by(
            trade_date=date(2026, 5, 8),
            universe_kind=UNIVERSE_KIND_MARKET,
            source=UNIVERSE_SOURCE_POLYGON_FLATFILE,
        )
        .order_by(UniverseDaily.ticker.asc())
        .all()
    )

    assert [row.ticker for row in rows] == ["AAA", "BBB"]
