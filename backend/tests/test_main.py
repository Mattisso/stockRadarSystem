from app.main import should_interval_refresh_polygon_day_aggregates


def test_should_interval_refresh_polygon_day_aggregates_enabled(monkeypatch):
    monkeypatch.setattr("app.main.settings.secret_universe_enabled", True)
    monkeypatch.setattr("app.main.settings.secret_universe_source", "polygon")
    monkeypatch.setattr("app.main.settings.polygon_day_aggregate_ingestion_enabled", True)
    monkeypatch.setattr("app.main.settings.polygon_day_aggregate_refresh_minutes", 15)

    assert should_interval_refresh_polygon_day_aggregates() is True


def test_should_interval_refresh_polygon_day_aggregates_disabled_without_polygon_source(monkeypatch):
    monkeypatch.setattr("app.main.settings.secret_universe_enabled", True)
    monkeypatch.setattr("app.main.settings.secret_universe_source", "broker")
    monkeypatch.setattr("app.main.settings.polygon_day_aggregate_ingestion_enabled", True)
    monkeypatch.setattr("app.main.settings.polygon_day_aggregate_refresh_minutes", 15)

    assert should_interval_refresh_polygon_day_aggregates() is False


def test_should_interval_refresh_polygon_day_aggregates_disabled_with_nonpositive_interval(monkeypatch):
    monkeypatch.setattr("app.main.settings.secret_universe_enabled", True)
    monkeypatch.setattr("app.main.settings.secret_universe_source", "polygon")
    monkeypatch.setattr("app.main.settings.polygon_day_aggregate_ingestion_enabled", True)
    monkeypatch.setattr("app.main.settings.polygon_day_aggregate_refresh_minutes", 0)

    assert should_interval_refresh_polygon_day_aggregates() is False
