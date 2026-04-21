from app.engine.secret_ingredients import SecretIngredientsService


def test_select_aggregate_subscription_tickers_uses_aggregate_defaults(monkeypatch):
    service = SecretIngredientsService(db=None)
    captured: dict[str, int] = {}

    def fake_select_live_subscription_tickers(*, max_symbols=None, min_avg_volume=None):
        captured["max_symbols"] = max_symbols
        captured["min_avg_volume"] = min_avg_volume
        return ["WLDS"]

    monkeypatch.setattr(service, "select_live_subscription_tickers", fake_select_live_subscription_tickers)
    monkeypatch.setattr("app.engine.secret_ingredients.settings.aggregate_live_max_symbols", 500)
    monkeypatch.setattr("app.engine.secret_ingredients.settings.aggregate_live_min_avg_volume", 0)

    tickers = service.select_aggregate_subscription_tickers()

    assert tickers == ["WLDS"]
    assert captured == {"max_symbols": 500, "min_avg_volume": 0}
