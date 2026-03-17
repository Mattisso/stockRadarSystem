"""Stock Radar System — FastAPI entry point."""

from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging import get_logger, setup_logging
from app.data.tick_buffer import TickBuffer
from app.engine.signal_detector import SignalDetector
from app.engine.trade_executor import TradeExecutor
from app.engine.universe_filter import UniverseFilterEngine
from app.risk.risk_manager import RiskManager

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    setup_logging()

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
    await broker.connect()
    app.state.broker = broker

    # ── Core components ─────────────────────────────────────────────
    tick_buffer = TickBuffer(maxlen=100)
    signal_detector = SignalDetector(tick_buffer)
    risk_manager = RiskManager(broker)
    trade_executor = TradeExecutor(
        broker=broker,
        tick_buffer=tick_buffer,
        signal_detector=signal_detector,
        risk_manager=risk_manager,
        db_session_factory=SessionLocal,
    )

    app.state.tick_buffer = tick_buffer
    app.state.signal_detector = signal_detector
    app.state.risk_manager = risk_manager
    app.state.trade_executor = trade_executor

    # ── Scheduler ───────────────────────────────────────────────────
    scheduler = AsyncIOScheduler()

    async def refresh_universe_job():
        db = SessionLocal()
        try:
            engine = UniverseFilterEngine(broker, db)
            tickers = await engine.refresh_universe()
            await broker.subscribe_market_data(tickers)
            log.info("scheduler.universe_refreshed", count=len(tickers))
        except Exception:
            log.exception("scheduler.universe_refresh_error")
        finally:
            db.close()

    async def scan_job():
        db = SessionLocal()
        try:
            engine = UniverseFilterEngine(broker, db)
            tickers = engine.get_active_tickers()
        finally:
            db.close()

        if not tickers:
            return

        await trade_executor.collect_market_data(tickers)
        await trade_executor.scan_signals(tickers)

    async def monitor_job():
        await trade_executor.monitor_positions()

    scheduler.add_job(refresh_universe_job, "interval", minutes=5, max_instances=1, id="universe_refresh")
    scheduler.add_job(scan_job, "interval", seconds=5, max_instances=1, id="signal_scan")
    scheduler.add_job(monitor_job, "interval", seconds=3, max_instances=1, id="position_monitor")

    scheduler.start()

    # Run initial universe refresh at startup
    await refresh_universe_job()

    log.info("app.started", trading_mode=settings.trading_mode)

    yield

    scheduler.shutdown(wait=False)
    await broker.disconnect()


app = FastAPI(
    title="Stock Radar System",
    description="AI-Powered Real-Time NASDAQ Breakout Detection & Execution",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Lock down in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
