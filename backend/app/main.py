"""Stock Radar System — FastAPI entry point."""

import asyncio
import time
from contextlib import asynccontextmanager

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
from app.core.metrics import ML_MODEL_TRAINED, SCHEDULER_JOB_DURATION, SCHEDULER_JOB_ERRORS
from app.core.orchestration import RuntimeOrchestrator
from app.data.tick_buffer import TickBuffer
from app.engine.signal_detector import SignalDetector
from app.engine.secret_ingredients import SecretIngredientsService
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    setup_logging()
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
    if settings.polygon_api_key:
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
        )
    app.state.polygon_client = polygon_client
    runtime.mark_service(
        "polygon",
        polygon_client is not None,
        detail=settings.polygon_mode if polygon_client else "disabled",
    )

    # ── Core components ─────────────────────────────────────────────
    from app.engine.breakout_engine import BreakoutEngine

    breakout_engine = BreakoutEngine(cache=cache)
    runtime.mark_service("breakout_engine", True)
    if polygon_client:
        from app.data.polygon_queue_consumer import BreakoutQueueConsumer

        polygon_queue_consumer = BreakoutQueueConsumer(polygon_queue, breakout_engine)
        await polygon_queue_consumer.start()
        await polygon_client.start()
        runtime.mark_service("polygon_queue_consumer", True)
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

    ws_manager = ConnectionManager(redis_url=settings.redis_url or None)
    await ws_manager.start()
    app.state.ws_manager = ws_manager

    app.state.breakout_engine = breakout_engine
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

    async def refresh_universe_job():
        start = time.monotonic()
        try:
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
            if not await ensure_broker_connected():
                return
            db = SessionLocal()
            try:
                engine = UniverseFilterEngine(broker, db)
                tickers = await engine.refresh_secret_ingredients_universe()
                if polygon_client:
                    polygon_client.update_subscriptions(tickers, source="secret_universe")
                log.info("scheduler.secret_universe_refreshed", count=len(tickers))
            finally:
                db.close()
        except Exception:
            SCHEDULER_JOB_ERRORS.labels(job="secret_universe_refresh").inc()
            log.exception("scheduler.secret_universe_refresh_error")
        finally:
            SCHEDULER_JOB_DURATION.labels(job="secret_universe_refresh").observe(time.monotonic() - start)

    async def scan_job():
        start = time.monotonic()
        try:
            if not broker.is_connected():
                return
            db = SessionLocal()
            try:
                engine = UniverseFilterEngine(broker, db)
                tickers = engine.get_active_tickers()
            finally:
                db.close()

            if not tickers:
                return

            # L1 breakout pre-filter: ingest from cache, scan for candidates
            await breakout_engine.ingest_from_cache(tickers)
            breakout_events = breakout_engine.scan(tickers)
            if breakout_events:
                db = SessionLocal()
                try:
                    secret_ingredients = SecretIngredientsService(db)
                    secret_ingredients.record_candidates(breakout_events)
                    secret_ingredients.record_l1_to_l2_events(breakout_events)
                    db.commit()
                except Exception:
                    db.rollback()
                    log.exception("secret_ingredients.persistence_error")
                finally:
                    db.close()

            # Deep analysis: only candidates from breakout engine + already-tracked tickers
            candidate_tickers = {e.ticker for e in breakout_events}
            tracked_tickers = {
                s.ticker for s in state_machine.all_states() if s.stage.value != "normal"
            }
            deep_tickers = list((candidate_tickers | tracked_tickers) & set(tickers))

            # Collect full market data (L1 + L2) for deep analysis tickers
            await trade_executor.collect_market_data(deep_tickers if deep_tickers else tickers)
            await trade_executor.scan_signals(deep_tickers if deep_tickers else tickers)

            # Broadcast signal + state_machine updates via WebSocket
            if ws_manager.active_count:
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
                            "timestamp": e.timestamp.isoformat(),
                        }
                        for e in breakout_events
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
            if ws_manager.active_count:
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

    scheduler.add_job(refresh_universe_job, "interval", minutes=5, max_instances=1, id="universe_refresh")
    if settings.secret_universe_enabled:
        scheduler.add_job(
            refresh_secret_universe_job,
            "cron",
            hour=settings.secret_universe_rebuild_hour,
            minute=settings.secret_universe_rebuild_minute,
            max_instances=1,
            id="secret_universe_refresh",
        )
    scheduler.add_job(scan_job, "interval", seconds=5, max_instances=1, id="signal_scan")
    scheduler.add_job(monitor_job, "interval", seconds=3, max_instances=1, id="position_monitor")
    scheduler.add_job(retrain_job, "interval", hours=settings.ml_retrain_interval_hours, max_instances=1, id="ml_retrain")

    scheduler.start()
    runtime.mark_service("scheduler", True)

    broker_task = asyncio.create_task(connect_broker_background())
    runtime.register_task("broker_connect", broker_task)
    # Kick off the first universe refresh after startup so health probes can succeed
    initial_refresh_task = asyncio.create_task(refresh_universe_job())
    runtime.register_task("initial_universe_refresh", initial_refresh_task)
    if settings.secret_universe_enabled:
        initial_secret_universe_task = asyncio.create_task(refresh_secret_universe_job())
        runtime.register_task("initial_secret_universe_refresh", initial_secret_universe_task)

    log.info("app.started", trading_mode=settings.trading_mode)

    yield

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

allowed_origins = [origin.strip() for origin in settings.cors_allowed_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from prometheus_fastapi_instrumentator import Instrumentator  # noqa: E402

Instrumentator(
    should_group_status_codes=False,
    excluded_handlers=["/metrics"],
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

app.include_router(public_router, prefix="/api")
app.include_router(router, prefix="/api")
app.include_router(ws_router, prefix="/api")
