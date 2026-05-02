from app.main import (
    current_runtime_role,
    should_enable_aggregate_rolling_refresh,
    should_enable_aggregate_client,
    should_enable_day_refresh,
    should_enable_ml_materialization_job,
    should_enable_minute_refresh,
    should_enable_position_monitor_job,
    should_enable_quote_client,
    should_interval_refresh_polygon_day_aggregates,
    should_run_background_jobs,
)


def test_current_runtime_role_normalizes_case(monkeypatch):
    monkeypatch.setattr("app.main.settings.api_runtime_role", "WoRkEr")

    assert current_runtime_role() == "worker"


def test_should_run_background_jobs_for_worker_role(monkeypatch):
    monkeypatch.setattr("app.main.settings.api_runtime_role", "worker")

    assert should_run_background_jobs() is True


def test_should_not_run_background_jobs_for_web_role(monkeypatch):
    monkeypatch.setattr("app.main.settings.api_runtime_role", "web")

    assert should_run_background_jobs() is False


def test_should_enable_quote_client(monkeypatch):
    monkeypatch.setattr("app.main.settings.api_runtime_role", "worker")
    monkeypatch.setattr("app.main.settings.polygon_api_key", "key")
    monkeypatch.setattr("app.main.settings.polygon_enable_quote_client", True)

    assert should_enable_quote_client() is True


def test_should_disable_quote_client_without_flag(monkeypatch):
    monkeypatch.setattr("app.main.settings.api_runtime_role", "worker")
    monkeypatch.setattr("app.main.settings.polygon_api_key", "key")
    monkeypatch.setattr("app.main.settings.polygon_enable_quote_client", False)

    assert should_enable_quote_client() is False


def test_should_enable_aggregate_client(monkeypatch):
    monkeypatch.setattr("app.main.settings.api_runtime_role", "worker")
    monkeypatch.setattr("app.main.settings.polygon_api_key", "key")
    monkeypatch.setattr("app.main.settings.polygon_enable_aggregate_client", True)

    assert should_enable_aggregate_client() is True


def test_should_enable_aggregate_rolling_refresh(monkeypatch):
    monkeypatch.setattr("app.main.settings.api_runtime_role", "worker")
    monkeypatch.setattr("app.main.settings.api_enable_aggregate_rolling_refresh", True)

    assert should_enable_aggregate_rolling_refresh() is True


def test_should_disable_position_monitor_job(monkeypatch):
    monkeypatch.setattr("app.main.settings.api_runtime_role", "worker")
    monkeypatch.setattr("app.main.settings.api_enable_position_monitor_job", False)

    assert should_enable_position_monitor_job() is False


def test_should_enable_day_refresh(monkeypatch):
    monkeypatch.setattr("app.main.settings.api_runtime_role", "worker")
    monkeypatch.setattr("app.main.settings.api_enable_day_refresh", True)

    assert should_enable_day_refresh() is True


def test_should_enable_minute_refresh(monkeypatch):
    monkeypatch.setattr("app.main.settings.api_runtime_role", "worker")
    monkeypatch.setattr("app.main.settings.api_enable_minute_refresh", True)

    assert should_enable_minute_refresh() is True


def test_should_enable_ml_materialization_job(monkeypatch):
    monkeypatch.setattr("app.main.settings.api_runtime_role", "worker")
    monkeypatch.setattr("app.main.settings.api_enable_ml_materialization_job", True)
    monkeypatch.setattr("app.main.settings.ml_materialization_interval_minutes", 15)

    assert should_enable_ml_materialization_job() is True


def test_should_disable_ml_materialization_job_with_nonpositive_interval(monkeypatch):
    monkeypatch.setattr("app.main.settings.api_runtime_role", "worker")
    monkeypatch.setattr("app.main.settings.api_enable_ml_materialization_job", True)
    monkeypatch.setattr("app.main.settings.ml_materialization_interval_minutes", 0)

    assert should_enable_ml_materialization_job() is False


def test_should_interval_refresh_polygon_day_aggregates_enabled(monkeypatch):
    monkeypatch.setattr("app.main.settings.api_runtime_role", "worker")
    monkeypatch.setattr("app.main.settings.secret_universe_enabled", True)
    monkeypatch.setattr("app.main.settings.secret_universe_source", "polygon")
    monkeypatch.setattr("app.main.settings.polygon_day_aggregate_ingestion_enabled", True)
    monkeypatch.setattr("app.main.settings.polygon_day_aggregate_refresh_minutes", 15)

    assert should_interval_refresh_polygon_day_aggregates() is True


def test_should_interval_refresh_polygon_day_aggregates_disabled_without_polygon_source(monkeypatch):
    monkeypatch.setattr("app.main.settings.api_runtime_role", "worker")
    monkeypatch.setattr("app.main.settings.secret_universe_enabled", True)
    monkeypatch.setattr("app.main.settings.secret_universe_source", "broker")
    monkeypatch.setattr("app.main.settings.polygon_day_aggregate_ingestion_enabled", True)
    monkeypatch.setattr("app.main.settings.polygon_day_aggregate_refresh_minutes", 15)

    assert should_interval_refresh_polygon_day_aggregates() is False


def test_should_interval_refresh_polygon_day_aggregates_disabled_with_nonpositive_interval(monkeypatch):
    monkeypatch.setattr("app.main.settings.api_runtime_role", "worker")
    monkeypatch.setattr("app.main.settings.secret_universe_enabled", True)
    monkeypatch.setattr("app.main.settings.secret_universe_source", "polygon")
    monkeypatch.setattr("app.main.settings.polygon_day_aggregate_ingestion_enabled", True)
    monkeypatch.setattr("app.main.settings.polygon_day_aggregate_refresh_minutes", 0)

    assert should_interval_refresh_polygon_day_aggregates() is False


def test_web_role_disables_polygon_clients_and_scheduler_helpers(monkeypatch):
    monkeypatch.setattr("app.main.settings.api_runtime_role", "web")
    monkeypatch.setattr("app.main.settings.polygon_api_key", "key")
    monkeypatch.setattr("app.main.settings.polygon_enable_quote_client", True)
    monkeypatch.setattr("app.main.settings.polygon_enable_aggregate_client", True)
    monkeypatch.setattr("app.main.settings.api_enable_aggregate_rolling_refresh", True)
    monkeypatch.setattr("app.main.settings.api_enable_day_refresh", True)
    monkeypatch.setattr("app.main.settings.api_enable_minute_refresh", True)
    monkeypatch.setattr("app.main.settings.api_enable_position_monitor_job", True)

    assert should_enable_quote_client() is False
    assert should_enable_aggregate_client() is False
    assert should_enable_aggregate_rolling_refresh() is False
    assert should_enable_day_refresh() is False
    assert should_enable_minute_refresh() is False
    assert should_enable_position_monitor_job() is False


def test_aggregate_decision_worker_can_enable_rolling_refresh_without_aggregate_client(monkeypatch):
    monkeypatch.setattr("app.main.settings.api_runtime_role", "worker")
    monkeypatch.setattr("app.main.settings.polygon_api_key", "")
    monkeypatch.setattr("app.main.settings.polygon_enable_aggregate_client", False)
    monkeypatch.setattr("app.main.settings.api_enable_aggregate_rolling_refresh", True)

    assert should_enable_aggregate_client() is False
    assert should_enable_aggregate_rolling_refresh() is True


def test_polygon_ingest_worker_can_enable_aggregate_client_without_rolling_refresh(monkeypatch):
    monkeypatch.setattr("app.main.settings.api_runtime_role", "worker")
    monkeypatch.setattr("app.main.settings.polygon_api_key", "key")
    monkeypatch.setattr("app.main.settings.polygon_enable_aggregate_client", True)
    monkeypatch.setattr("app.main.settings.api_enable_aggregate_rolling_refresh", False)

    assert should_enable_aggregate_client() is True
    assert should_enable_aggregate_rolling_refresh() is False
