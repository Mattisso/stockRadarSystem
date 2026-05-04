from datetime import date

from app.main import (
    current_runtime_role,
    resolve_polygon_minute_refresh_trade_date,
    should_enable_aggregate_rolling_refresh,
    should_enable_aggregate_client,
    should_enable_day_refresh,
    should_defer_nonessential_market_hours_jobs,
    should_enable_ml_materialization_job,
    should_enable_minute_refresh,
    should_enable_position_monitor_job,
    should_enable_quote_client,
    should_interval_refresh_polygon_day_aggregates,
    should_run_background_jobs,
)
from app.data.polygon_aggregate_service import PolygonAggregateService, PolygonDayAggregateRecord
from app.models.universe_daily import UniverseDaily


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


def test_should_defer_nonessential_market_hours_jobs(monkeypatch):
    monkeypatch.setattr("app.main.settings.api_runtime_role", "worker")
    monkeypatch.setattr("app.main.settings.api_prioritize_market_critical_jobs", True)
    monkeypatch.setattr("app.main.is_regular_us_market_hours", lambda now: True)

    assert should_defer_nonessential_market_hours_jobs() is True


def test_should_not_defer_nonessential_jobs_outside_market_hours(monkeypatch):
    monkeypatch.setattr("app.main.settings.api_runtime_role", "worker")
    monkeypatch.setattr("app.main.settings.api_prioritize_market_critical_jobs", True)
    monkeypatch.setattr("app.main.is_regular_us_market_hours", lambda now: False)

    assert should_defer_nonessential_market_hours_jobs() is False


def test_should_not_defer_nonessential_jobs_when_priority_policy_disabled(monkeypatch):
    monkeypatch.setattr("app.main.settings.api_runtime_role", "worker")
    monkeypatch.setattr("app.main.settings.api_prioritize_market_critical_jobs", False)
    monkeypatch.setattr("app.main.is_regular_us_market_hours", lambda now: True)

    assert should_defer_nonessential_market_hours_jobs() is False


def test_market_hours_priority_policy_does_not_disable_aggregate_rolling_refresh(monkeypatch):
    monkeypatch.setattr("app.main.settings.api_runtime_role", "worker")
    monkeypatch.setattr("app.main.settings.api_enable_aggregate_rolling_refresh", True)
    monkeypatch.setattr("app.main.settings.api_prioritize_market_critical_jobs", True)
    monkeypatch.setattr("app.main.is_regular_us_market_hours", lambda now: True)

    assert should_enable_aggregate_rolling_refresh() is True


def test_market_hours_priority_policy_does_not_disable_minute_refresh(monkeypatch):
    monkeypatch.setattr("app.main.settings.api_runtime_role", "worker")
    monkeypatch.setattr("app.main.settings.api_enable_minute_refresh", True)
    monkeypatch.setattr("app.main.settings.api_prioritize_market_critical_jobs", True)
    monkeypatch.setattr("app.main.is_regular_us_market_hours", lambda now: True)

    assert should_enable_minute_refresh() is True


def test_market_hours_priority_policy_does_not_disable_position_monitor(monkeypatch):
    monkeypatch.setattr("app.main.settings.api_runtime_role", "worker")
    monkeypatch.setattr("app.main.settings.api_enable_position_monitor_job", True)
    monkeypatch.setattr("app.main.settings.api_prioritize_market_critical_jobs", True)
    monkeypatch.setattr("app.main.is_regular_us_market_hours", lambda now: True)

    assert should_enable_position_monitor_job() is True


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


def test_resolve_polygon_minute_refresh_trade_date_prefers_latest_universe_snapshot(db):
    service = PolygonAggregateService(db)
    service.upsert_day_aggregates(
        [
            PolygonDayAggregateRecord(
                ticker="LCID",
                trade_date=date(2026, 5, 1),
                open=3.2,
                high=3.3,
                low=3.1,
                close=3.25,
                volume=100_000,
            )
        ]
    )
    db.add(
        UniverseDaily(
            trade_date=date(2026, 5, 4),
            ticker="LCID",
            open_price=3.2,
            last_price=3.25,
            avg_volume=100_000,
        )
    )
    db.commit()

    assert resolve_polygon_minute_refresh_trade_date(db) == date(2026, 5, 4)


def test_resolve_polygon_minute_refresh_trade_date_falls_back_to_day_aggregate_date(db):
    service = PolygonAggregateService(db)
    service.upsert_day_aggregates(
        [
            PolygonDayAggregateRecord(
                ticker="LCID",
                trade_date=date(2026, 5, 1),
                open=3.2,
                high=3.3,
                low=3.1,
                close=3.25,
                volume=100_000,
            )
        ]
    )
    db.commit()

    assert resolve_polygon_minute_refresh_trade_date(db) == date(2026, 5, 1)
