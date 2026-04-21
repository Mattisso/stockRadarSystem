from app.main import (
    should_enable_aggregate_rolling_refresh,
    should_enable_aggregate_client,
    should_enable_day_refresh,
    should_enable_minute_refresh,
    should_enable_position_monitor_job,
    should_enable_quote_client,
    should_interval_refresh_polygon_day_aggregates,
)


def test_should_enable_quote_client(monkeypatch):
    monkeypatch.setattr("app.main.settings.polygon_api_key", "key")
    monkeypatch.setattr("app.main.settings.polygon_enable_quote_client", True)

    assert should_enable_quote_client() is True


def test_should_disable_quote_client_without_flag(monkeypatch):
    monkeypatch.setattr("app.main.settings.polygon_api_key", "key")
    monkeypatch.setattr("app.main.settings.polygon_enable_quote_client", False)

    assert should_enable_quote_client() is False


def test_should_enable_aggregate_client(monkeypatch):
    monkeypatch.setattr("app.main.settings.polygon_api_key", "key")
    monkeypatch.setattr("app.main.settings.polygon_enable_aggregate_client", True)

    assert should_enable_aggregate_client() is True


def test_should_enable_aggregate_rolling_refresh(monkeypatch):
    monkeypatch.setattr("app.main.settings.polygon_api_key", "key")
    monkeypatch.setattr("app.main.settings.polygon_enable_aggregate_client", True)
    monkeypatch.setattr("app.main.settings.api_enable_aggregate_rolling_refresh", True)

    assert should_enable_aggregate_rolling_refresh() is True


def test_should_disable_position_monitor_job(monkeypatch):
    monkeypatch.setattr("app.main.settings.api_enable_position_monitor_job", False)

    assert should_enable_position_monitor_job() is False


def test_should_enable_day_refresh(monkeypatch):
    monkeypatch.setattr("app.main.settings.api_enable_day_refresh", True)

    assert should_enable_day_refresh() is True


def test_should_enable_minute_refresh(monkeypatch):
    monkeypatch.setattr("app.main.settings.polygon_api_key", "key")
    monkeypatch.setattr("app.main.settings.polygon_enable_aggregate_client", True)
    monkeypatch.setattr("app.main.settings.api_enable_minute_refresh", True)

    assert should_enable_minute_refresh() is True


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
