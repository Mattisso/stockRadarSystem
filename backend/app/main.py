"""Stock Radar System — FastAPI entry point."""

import asyncio
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, time as dt_time, timedelta, timezone
from zoneinfo import ZoneInfo

from apscheduler.events import (
    EVENT_JOB_ERROR,
    EVENT_JOB_EXECUTED,
    EVENT_JOB_MAX_INSTANCES,
    EVENT_JOB_MISSED,
    EVENT_JOB_SUBMITTED,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dataclasses import asdict

from app.api.routes import public_router, router
from app.api.websocket import router as ws_router
from app.api.ws_manager import ConnectionManager
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging import get_logger, setup_logging
from app.core.market_hours import is_regular_us_market_hours
from app.core.metrics import (
    ML_MODEL_TRAINED,
    SCHEDULER_JOB_DURATION,
    SCHEDULER_JOB_ERRORS,
    SECRET_ACTIVE_L2_SLOTS,
    SECRET_CANDIDATES_TOTAL,
    SECRET_HANDOFFS_TOTAL,
    SECRET_L2_PROMOTIONS_TOTAL,
    SECRET_L2_QUEUE_DEPTH,
    SECRET_UNIVERSE_SIZE,
)
from app.core.orchestration import RuntimeOrchestrator
from app.data.tick_buffer import TickBuffer
from app.data.polygon_aggregate_service import PolygonAggregateService
from app.data.aggregate_history_export_service import AggregateHistoryExportService
from app.data.polygon_live_retention_service import PolygonLiveRetentionService
from app.data.universe_loader import PolygonFlatFileUniverseLoader
from app.engine.aggregate_runtime_service import AggregateRuntimeService
from app.engine.signal_detector import SignalDetector
from app.engine.l1_feature_engine import L1FeatureEngine
from app.engine.l2_promotion_queue import L2PromotionQueue
from app.engine.secret_candidate_scorer import SecretCandidateScorer
from app.engine.secret_ingredients import SecretIngredientsService
from app.engine.secret_runtime_status import SecretIngredientsRuntimeStatus
from app.engine.secret_sauce_handoff import SecretSauceHandoffManager
from app.engine.state_machine import StateMachine
from app.engine.trade_executor import TradeExecutor
from app.engine.universe_filter import UniverseFilterEngine
from app.ml import BreakoutClassifier, MLScorer, ModelTrainer
from app.models.signal import Signal
from app.models.trade import Trade
from app.risk.risk_manager import RiskManager
from app.schemas.signal import SignalRead
from app.schemas.trade import TradeRead

log = get_logger(__name__)
NEW_YORK_TZ = ZoneInfo("America/New_York")


def current_runtime_role() -> str:
    return settings.api_runtime_role.lower()


def should_run_background_jobs() -> bool:
    return current_runtime_role() in {"all", "worker"}


def should_enable_quote_client() -> bool:
    return should_run_background_jobs() and bool(settings.polygon_api_key) and settings.polygon_enable_quote_client


def should_enable_aggregate_client() -> bool:
    return should_run_background_jobs() and bool(settings.polygon_api_key) and settings.polygon_enable_aggregate_client


def should_enable_position_monitor_job() -> bool:
    return should_run_background_jobs() and settings.api_enable_position_monitor_job


def should_enable_aggregate_rolling_refresh() -> bool:
    return should_run_background_jobs() and settings.api_enable_aggregate_rolling_refresh


def should_enable_day_refresh() -> bool:
    return should_run_background_jobs() and settings.api_enable_day_refresh


def should_enable_minute_refresh() -> bool:
    return should_run_background_jobs() and settings.api_enable_minute_refresh


def should_interval_refresh_polygon_day_aggregates() -> bool:
    return (
        settings.secret_universe_enabled
        and settings.secret_universe_source == "polygon"
        and settings.polygon_day_aggregate_ingestion_enabled
        and should_enable_day_refresh()
        and settings.polygon_day_aggregate_refresh_minutes > 0
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    setup_logging()
    runtime_role = current_runtime_role()
    run_background = should_run_background_jobs()
    runtime = RuntimeOrchestrator()
    app.state.runtime = runtime

    # ── Broker ──────────────────────────────────────────────────────
    if settings.broker_type == "ibkr":
        from app.broker.ibkr_broker import IBKRBroker

        broker = IBKRBroker(
            host=settings.ibkr_host,
            port=settings.ibkr_port,
            client_id=settings.ibkr_client_id,
            timeout=settings.ibkr_timeout,
            max_reconnect_attempts=settings.ibkr_max_reconnect_attempts,
        )
    else:
        from app.broker.mock_broker import MockBroker

        broker = MockBroker()
    app.state.broker = broker
    runtime.mark_service("broker", broker.is_connected(), detail=settings.broker_type)

    # ── ML components ────────────────────────────────────────────────
    classifier = BreakoutClassifier(model_dir=settings.ml_model_dir)
    classifier.load()  # try loading a previously saved model
    ML_MODEL_TRAINED.set(1 if classifier.is_trained else 0)

    ml_scorer = None
    if settings.ml_enabled:
        ml_scorer = MLScorer(classifier, weight=settings.ml_confidence_weight)

    trainer = ModelTrainer(classifier, SessionLocal, min_samples=settings.ml_min_training_samples)

    app.state.classifier = classifier
    app.state.trainer = trainer

    # ── Cache (Redis or in-memory) ───────────────────────────────────
    if settings.redis_url:
        from app.data.redis_cache import RedisCache

        cache = RedisCache(settings.redis_url, l1_ttl=settings.redis_l1_ttl, l2_ttl=settings.redis_l2_ttl)
    else:
        from app.data.cache import InMemoryCache

        cache = InMemoryCache(ttl=settings.redis_l1_ttl)
    await cache.connect()
    app.state.cache = cache
    runtime.mark_service("cache", await cache.is_healthy(), detail=type(cache).__name__)

    # ── Polygon L1 (optional) ────────────────────────────────────────
    polygon_client = None
    polygon_queue_consumer = None
    polygon_aggregate_client = None
    if should_enable_quote_client() or should_enable_aggregate_client():
        from app.data.polygon_client import PolygonClient

        polygon_queue = asyncio.Queue(maxsize=settings.polygon_queue_maxsize)
        polygon_client = PolygonClient(
            api_key=settings.polygon_api_key,
            mode=settings.polygon_mode,
            cache=cache,
            queue=polygon_queue,
            ws_url=settings.polygon_ws_url,
            rest_url=settings.polygon_rest_url,
            rest_poll_interval=settings.polygon_rest_poll_interval,
            reconnect_max_delay=settings.polygon_reconnect_max_delay,
            subscription_batch_size=settings.polygon_subscription_batch_size,
            dev_max_symbols=settings.polygon_dev_max_symbols,
            include_trade_wildcard=settings.secret_polygon_include_trade_wildcard,
            enable_quotes=should_enable_quote_client(),
            enable_aggregates=should_enable_aggregate_client() and settings.polygon_mode == "websocket",
            db_session_factory=SessionLocal if should_enable_aggregate_client() and settings.polygon_mode == "websocket" else None,
        )

        # Pre-hydrate subscriptions from database if symbols are already known
        db = SessionLocal()
        try:
            engine = UniverseFilterEngine(broker, db)
            active_tickers = engine.get_active_tickers()
            if (
                active_tickers
                and polygon_client is not None
                and not (settings.secret_universe_enabled and settings.secret_universe_source == "polygon")
            ):
                polygon_client.update_subscriptions(active_tickers, source="watchlist")

            if settings.secret_universe_enabled:
                aggregate_secret_tickers = SecretIngredientsService(db).select_aggregate_subscription_tickers()
                if aggregate_secret_tickers and polygon_client is not None:
                    polygon_client.update_subscriptions(aggregate_secret_tickers, source="secret_universe")
        except Exception:
            log.exception("polygon.pre_hydrate_error")
        finally:
            db.close()

    app.state.polygon_client = polygon_client
    app.state.polygon_aggregate_client = None
    runtime.mark_service(
        "polygon",
        polygon_client is not None and run_background,
        detail=(settings.polygon_mode if run_background else "disabled_for_web_role") if polygon_client else "disabled",
    )
    runtime.mark_service(
        "polygon_aggregates",
        polygon_client is not None and should_enable_aggregate_client() and run_background,
        detail=(settings.polygon_mode if run_background else "disabled_for_web_role")
        if polygon_client and should_enable_aggregate_client()
        else "disabled",
    )

    # ── Core components ─────────────────────────────────────────────
    from app.engine.breakout_engine import BreakoutEngine

    breakout_engine = BreakoutEngine(cache=cache)
    l1_feature_engine = L1FeatureEngine()
    secret_candidate_scorer = SecretCandidateScorer(
        min_score=settings.secret_candidate_min_score,
        max_spread_pct=settings.secret_candidate_max_spread_pct,
        min_quote_rate=settings.secret_candidate_min_quote_rate,
        min_buy_pressure=settings.secret_candidate_min_buy_pressure,
        min_volume_expansion=settings.secret_candidate_min_volume_expansion,
    )
    secret_sauce_handoffs = SecretSauceHandoffManager()
    secret_runtime_status = SecretIngredientsRuntimeStatus(
        configured_secret_universe_source=settings.secret_universe_source,
    )
    runtime.mark_service("breakout_engine", True)

    async def refresh_secret_universe_once(*, update_subscriptions: bool = True) -> tuple[str, list[str]]:
        db = SessionLocal()
        try:
            engine = UniverseFilterEngine(broker, db)
            source = settings.secret_universe_source
            if source == "polygon":
                if polygon_client is None:
                    raise RuntimeError("secret_universe_source=polygon but Polygon client is not configured")
                if settings.polygon_day_aggregate_ingestion_enabled:
                    try:
                        loader = PolygonFlatFileUniverseLoader(db)
                        trade_date, tickers, stats = loader.load_latest_universe_from_s3(
                            max_close=settings.secret_universe_max_price,
                            min_close=settings.secret_universe_min_price,
                        )
                        db.commit()
                        log.info(
                            "scheduler.polygon_flatfile_universe_refreshed",
                            trade_date=trade_date.isoformat(),
                            raw_count=stats.total_rows,
                            valid_count=stats.valid_rows,
                            filtered_count=stats.filtered_rows,
                            skipped_count=stats.skipped_rows,
                            universe_count=len(tickers),
                        )
                        source = "polygon_flatfile"
                    except Exception:
                        db.rollback()
                        aggregate_service = PolygonAggregateService(db)
                        trade_date, day_records = await resolve_polygon_trade_date_and_records(
                            polygon_client
                        )
                        inserted = aggregate_service.upsert_day_aggregates(day_records)
                        tickers = aggregate_service.build_daily_universe(
                            trade_date=trade_date,
                            max_close=settings.secret_universe_max_price,
                            min_close=settings.secret_universe_min_price,
                        )
                        db.commit()
                        log.warning(
                            "scheduler.polygon_universe_flatfile_unavailable_falling_back_to_grouped_rest",
                            trade_date=trade_date.isoformat(),
                            day_record_count=len(day_records),
                            inserted_count=inserted,
                            universe_count=len(tickers),
                        )
                        source = "polygon_grouped_day_rest"
                else:
                    universe_quotes = await polygon_client.load_reference_universe(
                        max_price=settings.secret_universe_max_price,
                        min_price=settings.secret_universe_min_price,
                        min_volume=settings.secret_universe_min_volume,
                    )
                    tickers = await engine.refresh_secret_ingredients_universe(universe_quotes=universe_quotes)
            else:
                tickers = await engine.refresh_secret_ingredients_universe()

            aggregate_tickers = SecretIngredientsService(db).select_aggregate_subscription_tickers()
            live_tickers = SecretIngredientsService(db).select_live_subscription_tickers()
            if update_subscriptions:
                if polygon_client:
                    if settings.secret_universe_source == "polygon":
                        polygon_client.update_subscriptions([], source="watchlist")
                    polygon_client.update_subscriptions(aggregate_tickers, source="secret_universe")
            SECRET_UNIVERSE_SIZE.set(len(tickers))
            secret_runtime_status.mark_secret_universe_refresh(len(tickers), source=source)
            return source, tickers, live_tickers
        finally:
            db.close()

    if run_background and settings.secret_universe_enabled and settings.secret_universe_source == "polygon":
        try:
            source, tickers, live_tickers = await refresh_secret_universe_once(update_subscriptions=True)
            log.info(
                "startup.secret_universe_hydrated",
                count=len(tickers),
                live_count=len(live_tickers),
                source=source,
            )
        except Exception:
            secret_runtime_status.mark_error("startup_secret_universe_refresh_error")
            log.exception("startup.secret_universe_hydration_error")

    if polygon_client and (should_enable_quote_client() or should_enable_aggregate_client()):
        from app.data.polygon_queue_consumer import BreakoutQueueConsumer
        from app.data.polygon_tick_persister import PolygonTickPersister

        tick_persister = None
        if should_enable_quote_client() and settings.polygon_persist_ticks:
            tick_persister = PolygonTickPersister(
                SessionLocal,
                batch_size=settings.polygon_persist_batch_size,
            )
        if should_enable_quote_client():
            polygon_queue_consumer = BreakoutQueueConsumer(
                polygon_queue,
                breakout_engine,
                l1_feature_engine=l1_feature_engine,
                tick_persister=tick_persister,
            )
        if run_background:
            if settings.polygon_mode == "websocket" and not is_regular_us_market_hours(datetime.now(timezone.utc)):
                await polygon_client.pause_subscriptions()
            if polygon_queue_consumer is not None:
                await polygon_queue_consumer.start()
            await polygon_client.start()
        runtime.mark_service(
            "polygon_queue_consumer",
            polygon_queue_consumer is not None and run_background,
            detail="enabled" if polygon_queue_consumer is not None and run_background else "disabled",
        )
    else:
        runtime.mark_service("polygon_queue_consumer", False, detail="disabled")
    tick_buffer = TickBuffer(maxlen=100)
    signal_detector = SignalDetector(tick_buffer, ml_scorer=ml_scorer)
    risk_manager = RiskManager(broker)
    state_machine = StateMachine(
        tick_buffer=tick_buffer,
        signal_detector=signal_detector,
        broker=broker,
    )
    trade_executor = TradeExecutor(
        broker=broker,
        tick_buffer=tick_buffer,
        signal_detector=signal_detector,
        risk_manager=risk_manager,
        db_session_factory=SessionLocal,
        state_machine=state_machine,
        cache=cache,
    )
    secret_l2_promotion_queue = L2PromotionQueue(
        state_machine.l2_manager,
        max_active=settings.secret_l2_max_active,
        max_queue_size=settings.secret_l2_queue_maxsize,
    )

    ws_manager = ConnectionManager(redis_url=settings.redis_url or None)
    await ws_manager.start()
    app.state.ws_manager = ws_manager

    app.state.breakout_engine = breakout_engine
    app.state.l1_feature_engine = l1_feature_engine
    app.state.secret_candidate_scorer = secret_candidate_scorer
    app.state.secret_sauce_handoffs = secret_sauce_handoffs
    app.state.secret_l2_promotion_queue = secret_l2_promotion_queue
    app.state.secret_runtime_status = secret_runtime_status
    app.state.tick_buffer = tick_buffer
    app.state.signal_detector = signal_detector
    app.state.state_machine = state_machine
    app.state.risk_manager = risk_manager
    app.state.trade_executor = trade_executor
    app.state.polygon_queue_consumer = polygon_queue_consumer
    app.state.secret_ingredients = SecretIngredientsService
    runtime.mark_service("state_machine", True)
    runtime.mark_service("agents", True)

    async def ensure_broker_connected() -> bool:
        if broker.is_connected():
            runtime.mark_service("broker", True, detail=settings.broker_type)
            return True
        try:
            await broker.connect()
            runtime.mark_service("broker", True, detail=settings.broker_type)
            return True
        except Exception:
            runtime.mark_service("broker", False, detail="connect_failed")
            log.exception("broker.connect_failed")
            return False

    async def connect_broker_background() -> None:
        while not broker.is_connected():
            connected = await ensure_broker_connected()
            if connected:
                return
            await asyncio.sleep(5)

    # ── Scheduler ───────────────────────────────────────────────────
    scheduler = AsyncIOScheduler()
    use_polygon_secret_universe = settings.secret_universe_enabled and settings.secret_universe_source == "polygon"
    secret_universe_job_ids = {"secret_universe_refresh", "secret_universe_refresh_interval"}

    def _log_secret_universe_job_registration(job_id: str) -> None:
        job = scheduler.get_job(job_id)
        if job is None:
            log.warning("scheduler.secret_universe_job_missing_after_registration", job_id=job_id)
            return
        next_run_time = getattr(job, "next_run_time", None)
        log.info(
            "scheduler.secret_universe_job_registered",
            job_id=job.id,
            trigger=str(job.trigger),
            next_run_time=next_run_time.isoformat() if next_run_time else None,
        )

    def _secret_universe_job_listener(event) -> None:
        job_id = getattr(event, "job_id", None)
        if job_id not in secret_universe_job_ids:
            return
        if event.code == EVENT_JOB_SUBMITTED:
            log.info("scheduler.secret_universe_job_submitted", job_id=job_id)
        elif event.code == EVENT_JOB_EXECUTED:
            log.info("scheduler.secret_universe_job_executed", job_id=job_id)
        elif event.code == EVENT_JOB_ERROR:
            log.error(
                "scheduler.secret_universe_job_failed",
                job_id=job_id,
                exception=repr(getattr(event, "exception", None)),
            )
        elif event.code == EVENT_JOB_MISSED:
            log.warning(
                "scheduler.secret_universe_job_missed",
                job_id=job_id,
                scheduled_run_time=event.scheduled_run_time.isoformat() if event.scheduled_run_time else None,
            )
        elif event.code == EVENT_JOB_MAX_INSTANCES:
            scheduled_times = [
                run_time.isoformat()
                for run_time in getattr(event, "scheduled_run_times", []) or []
            ]
            log.warning(
                "scheduler.secret_universe_job_max_instances",
                job_id=job_id,
                scheduled_run_times=scheduled_times,
            )

    scheduler.add_listener(
        _secret_universe_job_listener,
        EVENT_JOB_SUBMITTED | EVENT_JOB_EXECUTED | EVENT_JOB_ERROR | EVENT_JOB_MISSED | EVENT_JOB_MAX_INSTANCES,
    )

    async def refresh_universe_job():
        start = time.monotonic()
        try:
            if use_polygon_secret_universe:
                log.info("scheduler.universe_refresh_skipped", reason="polygon_secret_universe_enabled")
                return
            if not await ensure_broker_connected():
                return
            db = SessionLocal()
            try:
                engine = UniverseFilterEngine(broker, db)
                tickers = await engine.refresh_universe()
                await broker.subscribe_market_data(tickers)
                if polygon_client:
                    polygon_client.update_subscriptions(tickers, source="watchlist")
                log.info("scheduler.universe_refreshed", count=len(tickers))
            finally:
                db.close()
        except Exception:
            SCHEDULER_JOB_ERRORS.labels(job="universe_refresh").inc()
            log.exception("scheduler.universe_refresh_error")
        finally:
            SCHEDULER_JOB_DURATION.labels(job="universe_refresh").observe(time.monotonic() - start)

    async def refresh_secret_universe_job():
        start = time.monotonic()
        try:
            if not settings.secret_universe_enabled:
                return
            source, tickers, live_tickers = await refresh_secret_universe_once(update_subscriptions=True)
            log.info(
                "scheduler.secret_universe_refreshed",
                count=len(tickers),
                live_count=len(live_tickers),
                source=source,
            )
        except Exception:
            SCHEDULER_JOB_ERRORS.labels(job="secret_universe_refresh").inc()
            secret_runtime_status.mark_error("secret_universe_refresh_error")
            log.exception("scheduler.secret_universe_refresh_error")
        finally:
            SCHEDULER_JOB_DURATION.labels(job="secret_universe_refresh").observe(time.monotonic() - start)

    async def refresh_polygon_minute_aggregates_job():
        start = time.monotonic()
        try:
            if not settings.polygon_minute_aggregate_ingestion_enabled:
                return
            if polygon_client is None:
                return
            db = SessionLocal()
            try:
                aggregate_service = PolygonAggregateService(db)
                tickers = SecretIngredientsService(db).select_aggregate_subscription_tickers()
                if not tickers:
                    return
                trade_date = aggregate_service.latest_day_aggregate_date()
                if trade_date is None:
                    return
                allowed_tickers = set(tickers)
                inserted = 0
                for ticker in tickers:
                    minute_records = await polygon_client.fetch_minute_aggregates_for_ticker(
                        ticker,
                        trade_date=trade_date,
                    )
                    inserted += aggregate_service.upsert_minute_aggregates(
                        minute_records,
                        allowed_tickers=allowed_tickers,
                    )
                db.commit()
                log.info(
                    "scheduler.polygon_minute_aggregates_refreshed",
                    trade_date=trade_date.isoformat(),
                    ticker_count=len(tickers),
                    inserted_count=inserted,
                )
            finally:
                db.close()
        except Exception:
            SCHEDULER_JOB_ERRORS.labels(job="polygon_minute_aggregates_refresh").inc()
            log.exception("scheduler.polygon_minute_aggregates_refresh_error")
        finally:
            SCHEDULER_JOB_DURATION.labels(job="polygon_minute_aggregates_refresh").observe(
                time.monotonic() - start
            )

    async def resolve_polygon_trade_date_and_records(
        client,
        *,
        max_lookback_days: int = 7,
    ) -> tuple[date, list]:
        """Pick the most recent trade date with grouped bars available.

        This avoids weekend/holiday failures and avoids assuming `date.today()`
        is always a valid grouped-aggregate trading date.
        """
        ny_now = datetime.now(NEW_YORK_TZ)
        candidate = ny_now.date()
        if ny_now.time() < dt_time(9, 30):
            candidate -= timedelta(days=1)

        for _ in range(max_lookback_days):
            if candidate.weekday() >= 5:
                candidate -= timedelta(days=1)
                continue

            records = await client.fetch_grouped_day_aggregates(candidate)
            if records:
                return candidate, records

            candidate -= timedelta(days=1)

        raise RuntimeError("No Polygon grouped day aggregates found in lookback window")

    async def scan_job():
        start = time.monotonic()
        try:
            if not settings.api_enable_legacy_scan_job:
                return
            db = SessionLocal()
            try:
                engine = UniverseFilterEngine(broker, db)
                if settings.secret_universe_enabled:
                    tickers = engine.get_secret_ingredients_tickers()
                else:
                    tickers = engine.get_active_tickers()
            finally:
                db.close()

            if not tickers:
                return

            # L1 pre-filter and Secret Ingredients scoring
            await breakout_engine.ingest_from_cache(tickers)
            await l1_feature_engine.ingest_from_cache(cache, tickers)
            breakout_events = breakout_engine.scan(tickers)
            candidate_events = secret_candidate_scorer.score_snapshots(
                l1_feature_engine.snapshots(tickers)
            )
            if candidate_events:
                SECRET_CANDIDATES_TOTAL.inc(len(candidate_events))
                handoffs = secret_sauce_handoffs.emit(candidate_events)
                SECRET_HANDOFFS_TOTAL.inc(len(handoffs))
                secret_l2_promotion_queue.enqueue(handoffs)
                promoted = await secret_l2_promotion_queue.drain_once()
                queue_snapshot = secret_l2_promotion_queue.snapshot()
                SECRET_L2_QUEUE_DEPTH.set(queue_snapshot["queue_depth"])
                SECRET_ACTIVE_L2_SLOTS.set(queue_snapshot["active_count"])
                if promoted:
                    SECRET_L2_PROMOTIONS_TOTAL.inc(len(promoted))
                for ticker in state_machine.l2_manager.active_symbols:
                    if state_machine.l2_manager._active.get(ticker, None) and state_machine.l2_manager._active[ticker].confirmed:
                        secret_l2_promotion_queue.mark_confirmed(ticker)
                secret_runtime_status.mark_scan(
                    candidates=len(candidate_events),
                    handoffs=len(handoffs),
                    promotions=len(promoted),
                    promoted_tickers=promoted,
                )
                log.info(
                    "secret_ingredients.scan_summary",
                    candidate_count=len(candidate_events),
                    handoff_count=len(handoffs),
                    promotion_count=len(promoted),
                    queue_depth=queue_snapshot["queue_depth"],
                    active_slots=queue_snapshot["active_count"],
                )
                db = SessionLocal()
                try:
                    secret_ingredients = SecretIngredientsService(db)
                    secret_ingredients.record_candidates(candidate_events)
                    secret_ingredients.record_l1_to_l2_events(candidate_events)
                    db.commit()
                except Exception:
                    db.rollback()
                    secret_runtime_status.mark_error("secret_ingredients.persistence_error")
                    log.exception("secret_ingredients.persistence_error")
                finally:
                    db.close()
            else:
                secret_l2_promotion_queue.drop_stale_or_invalidated()
                queue_snapshot = secret_l2_promotion_queue.snapshot()
                SECRET_L2_QUEUE_DEPTH.set(queue_snapshot["queue_depth"])
                SECRET_ACTIVE_L2_SLOTS.set(queue_snapshot["active_count"])
                secret_runtime_status.mark_scan(
                    candidates=0,
                    handoffs=0,
                    promotions=0,
                    promoted_tickers=[],
                )
                log.info(
                    "secret_ingredients.scan_summary",
                    candidate_count=0,
                    handoff_count=0,
                    promotion_count=0,
                    queue_depth=queue_snapshot["queue_depth"],
                    active_slots=queue_snapshot["active_count"],
                )

            # Deep analysis: Secret Ingredients candidates + existing tracked tickers
            candidate_tickers = {e.ticker for e in candidate_events}
            tracked_tickers = {
                s.ticker for s in state_machine.all_states() if s.stage.value != "normal"
            }
            deep_tickers = list((candidate_tickers | tracked_tickers) & set(tickers))

            # Collect full market data (L1 + L2) for deep analysis tickers
            await trade_executor.collect_market_data(deep_tickers if deep_tickers else tickers)
            await trade_executor.scan_signals(deep_tickers if deep_tickers else tickers)

            # Broadcast signal + state_machine updates via WebSocket
            if ws_manager.active_count or ws_manager.uses_pubsub:
                try:
                    db = SessionLocal()
                    try:
                        signals = db.query(Signal).order_by(Signal.created_at.desc()).limit(50).all()
                        await ws_manager.broadcast(
                            "signal",
                            [SignalRead.model_validate(s).model_dump(mode="json") for s in signals],
                            channel="signals",
                        )
                    finally:
                        db.close()

                    states = [
                        {
                            "ticker": s.ticker,
                            "stage": s.stage.value,
                            "score": round(s.score, 4),
                            "entered_at": s.entered_at.isoformat(),
                            "consecutive_ticks": s.consecutive_ticks,
                            "decay_ticks": s.decay_ticks,
                            "reason": s.reason,
                        }
                        for s in state_machine.all_states()
                        if s.stage.value != "normal"
                    ]
                    await ws_manager.broadcast("state_machine", states, channel="signals")

                    live_movers = [
                        {
                            "ticker": e.ticker,
                            "breakout_score": e.breakout_score,
                            "pct_change_1m": e.pct_change_1m,
                            "pct_change_5m": e.pct_change_5m,
                            "volume_ratio": e.volume_ratio,
                            "spread_pct": e.spread_pct,
                            "quote_rate": e.quote_rate,
                            "buy_pressure": e.buy_pressure,
                            "timestamp": e.timestamp.isoformat(),
                        }
                        for e in candidate_events
                    ]
                    await ws_manager.broadcast("live_movers", live_movers, channel="l1")

                    l2_books = []
                    for ticker in deep_tickers:
                        latest = tick_buffer.get_latest(ticker)
                        if latest is None or latest.order_book is None:
                            continue
                        l2_books.append(
                            {
                                "ticker": latest.order_book.ticker,
                                "timestamp": latest.order_book.timestamp.isoformat(),
                                "bids": [asdict(level) for level in latest.order_book.bids[:10]],
                                "asks": [asdict(level) for level in latest.order_book.asks[:10]],
                            }
                        )
                    await ws_manager.broadcast("l2", l2_books, channel="l2")
                except Exception:
                    log.exception("ws.broadcast_scan_error")
        except Exception:
            SCHEDULER_JOB_ERRORS.labels(job="signal_scan").inc()
            secret_runtime_status.mark_error("signal_scan_error")
            log.exception("scheduler.signal_scan_error")
        finally:
            SCHEDULER_JOB_DURATION.labels(job="signal_scan").observe(time.monotonic() - start)

    async def monitor_job():
        start = time.monotonic()
        try:
            if not broker.is_connected():
                return
            await trade_executor.monitor_positions()

            # Broadcast trade + portfolio updates via WebSocket
            if ws_manager.active_count or ws_manager.uses_pubsub:
                try:
                    db = SessionLocal()
                    try:
                        trades = db.query(Trade).order_by(Trade.created_at.desc()).limit(50).all()
                        await ws_manager.broadcast(
                            "trade",
                            [TradeRead.model_validate(t).model_dump(mode="json") for t in trades],
                            channel="trades",
                        )
                    finally:
                        db.close()

                    summary = await broker.get_account_summary()
                    await ws_manager.broadcast("portfolio", asdict(summary), channel="trades")
                except Exception:
                    log.exception("ws.broadcast_monitor_error")
        except Exception:
            SCHEDULER_JOB_ERRORS.labels(job="position_monitor").inc()
            log.exception("scheduler.position_monitor_error")
        finally:
            SCHEDULER_JOB_DURATION.labels(job="position_monitor").observe(time.monotonic() - start)

    async def retrain_job():
        start = time.monotonic()
        try:
            await trainer.retrain_if_needed()
        except Exception:
            SCHEDULER_JOB_ERRORS.labels(job="ml_retrain").inc()
            log.exception("scheduler.ml_retrain_error")
        finally:
            SCHEDULER_JOB_DURATION.labels(job="ml_retrain").observe(time.monotonic() - start)

    async def polygon_live_retention_job():
        start = time.monotonic()
        try:
            db = SessionLocal()
            try:
                result = PolygonLiveRetentionService(db).purge(
                    tick_retention_hours=settings.polygon_live_ticks_retention_hours,
                    minute_retention_hours=settings.polygon_live_minute_aggregates_retention_hours,
                    second_retention_hours=settings.polygon_live_second_aggregates_retention_hours,
                )
                db.commit()
                log.info(
                    "scheduler.polygon_live_retention_completed",
                    deleted_tick_rows=result.deleted_tick_rows,
                    deleted_minute_rows=result.deleted_minute_rows,
                    deleted_second_rows=result.deleted_second_rows,
                    tick_cutoff_ts=result.tick_cutoff_ts.isoformat(),
                    minute_cutoff_ts=result.minute_cutoff_ts.isoformat(),
                    second_cutoff_ts=result.second_cutoff_ts.isoformat(),
                )
            finally:
                db.close()
        except Exception:
            SCHEDULER_JOB_ERRORS.labels(job="polygon_live_retention").inc()
            log.exception("scheduler.polygon_live_retention_error")
        finally:
            SCHEDULER_JOB_DURATION.labels(job="polygon_live_retention").observe(time.monotonic() - start)

    async def aggregate_rolling_refresh_job():
        start = time.monotonic()
        try:
            db = SessionLocal()
            try:
                result = AggregateRuntimeService(db).refresh_validation_and_decisions(
                    as_of=datetime.now(timezone.utc),
                )
                db.commit()
                log.info(
                    "scheduler.aggregate_rolling_refresh_completed",
                    refreshed_state_count=result.refreshed_state_count,
                    refreshed_validation_count=result.refreshed_validation_count,
                    persisted_decision_count=result.persisted_decision_count,
                    processed_candidate_event_count=result.processed_candidate_event_count,
                    as_of=result.as_of.isoformat(),
                )
            finally:
                db.close()
        except Exception:
            SCHEDULER_JOB_ERRORS.labels(job="aggregate_rolling_refresh").inc()
            log.exception("scheduler.aggregate_rolling_refresh_error")
        finally:
            SCHEDULER_JOB_DURATION.labels(job="aggregate_rolling_refresh").observe(time.monotonic() - start)

    async def aggregate_history_export_job():
        start = time.monotonic()
        try:
            if not settings.aggregate_history_export_enabled:
                return
            db = SessionLocal()
            try:
                result = AggregateHistoryExportService(db).export_jsonl(
                    output_dir=settings.aggregate_history_export_dir,
                    min_age_minutes=settings.aggregate_history_export_min_age_minutes,
                    now=datetime.now(timezone.utc),
                )
                log.info(
                    "scheduler.aggregate_history_export_completed",
                    export_dir=str(result.export_dir),
                    cutoff_ts=result.cutoff_ts.isoformat(),
                    cutoff_date=result.cutoff_date.isoformat(),
                    universe_rows=result.universe_rows,
                    minute_rows=result.minute_rows,
                    second_rows=result.second_rows,
                    candidate_rows=result.candidate_rows,
                    decision_rows=result.decision_rows,
                )
            finally:
                db.close()
        except Exception:
            SCHEDULER_JOB_ERRORS.labels(job="aggregate_history_export").inc()
            log.exception("scheduler.aggregate_history_export_error")
        finally:
            SCHEDULER_JOB_DURATION.labels(job="aggregate_history_export").observe(time.monotonic() - start)

    async def sync_polygon_market_hours_subscriptions_job():
        start = time.monotonic()
        try:
            if polygon_client is None or settings.polygon_mode != "websocket":
                return
            if is_regular_us_market_hours(datetime.now(timezone.utc)):
                await polygon_client.resume_subscriptions()
            else:
                await polygon_client.pause_subscriptions()
        except Exception:
            SCHEDULER_JOB_ERRORS.labels(job="polygon_market_hours_subscriptions").inc()
            log.exception("scheduler.polygon_market_hours_subscriptions_error")
        finally:
            SCHEDULER_JOB_DURATION.labels(job="polygon_market_hours_subscriptions").observe(
                time.monotonic() - start
            )

    if run_background:
        if not use_polygon_secret_universe:
            scheduler.add_job(refresh_universe_job, "interval", minutes=5, max_instances=1, id="universe_refresh")
        if settings.secret_universe_enabled and should_enable_day_refresh():
            scheduler.add_job(
                refresh_secret_universe_job,
                "cron",
                hour=settings.secret_universe_rebuild_hour,
                minute=settings.secret_universe_rebuild_minute,
                max_instances=1,
                id="secret_universe_refresh",
            )
            _log_secret_universe_job_registration("secret_universe_refresh")
            if should_interval_refresh_polygon_day_aggregates():
                scheduler.add_job(
                    refresh_secret_universe_job,
                    "interval",
                    minutes=settings.polygon_day_aggregate_refresh_minutes,
                    max_instances=1,
                    id="secret_universe_refresh_interval",
                )
                _log_secret_universe_job_registration("secret_universe_refresh_interval")
        if should_enable_minute_refresh() and settings.polygon_minute_aggregate_ingestion_enabled:
            scheduler.add_job(
                refresh_polygon_minute_aggregates_job,
                "interval",
                minutes=settings.polygon_minute_aggregate_refresh_minutes,
                max_instances=1,
                id="polygon_minute_aggregates_refresh",
            )
        scheduler.add_job(
            polygon_live_retention_job,
            "interval",
            minutes=settings.polygon_live_cleanup_interval_minutes,
            max_instances=1,
            id="polygon_live_retention",
        )
        if polygon_client is not None and settings.polygon_mode == "websocket":
            scheduler.add_job(
                sync_polygon_market_hours_subscriptions_job,
                "interval",
                minutes=1,
                max_instances=1,
                id="polygon_market_hours_subscriptions",
            )
        if should_enable_aggregate_rolling_refresh():
            scheduler.add_job(
                aggregate_rolling_refresh_job,
                "interval",
                seconds=settings.aggregate_rolling_refresh_seconds,
                max_instances=1,
                id="aggregate_rolling_refresh",
            )
            scheduler.add_job(
                aggregate_history_export_job,
                "interval",
                minutes=settings.aggregate_history_export_interval_minutes,
                max_instances=1,
                id="aggregate_history_export",
            )
        if settings.api_enable_legacy_scan_job:
            scheduler.add_job(scan_job, "interval", seconds=5, max_instances=1, id="signal_scan")
        if should_enable_position_monitor_job():
            scheduler.add_job(monitor_job, "interval", seconds=3, max_instances=1, id="position_monitor")
        scheduler.add_job(
            retrain_job,
            "interval",
            hours=settings.ml_retrain_interval_hours,
            max_instances=1,
            id="ml_retrain",
        )

        scheduler.start()
        runtime.mark_service("scheduler", True)

        broker_task = asyncio.create_task(connect_broker_background())
        runtime.register_task("broker_connect", broker_task)
        # Kick off the first universe refresh after startup so background state is hydrated immediately.
        if not use_polygon_secret_universe:
            initial_refresh_task = asyncio.create_task(refresh_universe_job())
            runtime.register_task("initial_universe_refresh", initial_refresh_task)
        if settings.secret_universe_enabled and should_enable_day_refresh():
            initial_secret_universe_task = asyncio.create_task(refresh_secret_universe_job())
            runtime.register_task("initial_secret_universe_refresh", initial_secret_universe_task)
        if should_enable_minute_refresh() and settings.polygon_minute_aggregate_ingestion_enabled:
            initial_polygon_minute_task = asyncio.create_task(refresh_polygon_minute_aggregates_job())
            runtime.register_task("initial_polygon_minute_aggregates_refresh", initial_polygon_minute_task)
        if polygon_client is not None and settings.polygon_mode == "websocket":
            initial_market_hours_subscription_task = asyncio.create_task(sync_polygon_market_hours_subscriptions_job())
            runtime.register_task("initial_polygon_market_hours_subscriptions", initial_market_hours_subscription_task)
        if should_enable_aggregate_rolling_refresh():
            initial_aggregate_refresh_task = asyncio.create_task(aggregate_rolling_refresh_job())
            runtime.register_task("initial_aggregate_rolling_refresh", initial_aggregate_refresh_task)
        if should_enable_aggregate_rolling_refresh() and settings.aggregate_history_export_enabled:
            initial_history_export_task = asyncio.create_task(aggregate_history_export_job())
            runtime.register_task("initial_aggregate_history_export", initial_history_export_task)
    else:
        runtime.mark_service("scheduler", True, detail="disabled_for_web_role")

    log.info("app.started", trading_mode=settings.trading_mode, runtime_role=runtime_role)

    yield

    if run_background:
        scheduler.shutdown(wait=False)
    if polygon_client:
        await polygon_client.stop()
    if polygon_queue_consumer:
        await polygon_queue_consumer.stop()
    await cache.disconnect()
    await ws_manager.stop()
    runtime.mark_service("cache", False, detail="shutdown")
    runtime.mark_service("scheduler", False, detail="shutdown")
    await runtime.shutdown_tasks()
    if broker.is_connected():
        await broker.disconnect()
    runtime.mark_service("broker", False, detail="shutdown")


app = FastAPI(
    title="Stock Radar System",
    description="AI-Powered Real-Time NASDAQ Breakout Detection & Execution",
    version="0.1.0",
    lifespan=lifespan,
)

from app.api.observability import ApiObservabilityMiddleware
app.add_middleware(ApiObservabilityMiddleware)

allowed_origins = [origin.strip() for origin in settings.cors_allowed_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=settings.cors_allowed_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Curl", "X-Tables", "X-Response-Time-Ms"],
)

from prometheus_fastapi_instrumentator import Instrumentator  # noqa: E402

Instrumentator(
    should_group_status_codes=False,
    excluded_handlers=["/metrics"],
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


@app.get("/", include_in_schema=False)
async def root():
    return {
        "status": "ok",
        "name": "Stock Radar System API",
        "docs": "/docs",
        "health": "/api/health",
        "metrics": "/metrics",
    }


app.include_router(public_router, prefix="/api")
app.include_router(router, prefix="/api")
app.include_router(ws_router, prefix="/api")
