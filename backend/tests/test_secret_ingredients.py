from app.engine.secret_ingredients import SecretIngredientsService


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
