"""REST API routes for Stock Radar System."""

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.auth import (
    TokenRequest,
    TokenResponse,
    create_access_token,
    require_auth,
)
from app.core.config import settings
from app.core.database import get_db
from app.api.dependencies import get_broker, get_runtime, get_state_machine
from app.ml.analytics import TradeAnalytics
from app.ml.backtest import BacktestConfig, SignalBacktester
from app.engine.secret_candidate_scorer import SecretCandidateScorer
from app.engine.secret_replay_validator import SecretReplayValidator, build_replay_quote
from app.models.signal import Signal
from app.models.symbol import Symbol
from app.models.trade import Trade
from app.schemas.ml import (
    ApiContractResponse,
    BacktestRequest,
    BacktestResponse,
    KPIResponse,
    MLStatusResponse,
    RetrainResponse,
    SecretSauceContractResponse,
    SecretSauceHandoffResponse,
    SecretSauceStatusResponse,
    SecretSauceQueueStatusResponse,
    SecretReplayRequest,
    SecretReplayResponse,
    SignalAccuracyBucketResponse,
)
from app.schemas.signal import SignalRead
from app.schemas.symbol import SymbolRead
from app.schemas.trade import TradeRead

# ── Public routes (no auth) ──────────────────────────────────────────

public_router = APIRouter()


@public_router.get("/health")
async def health_check(request: Request):
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None:
        return {"status": "ok"}
    services = runtime.snapshot()["services"]
    healthy = all(service["healthy"] for service in services.values()) if services else True
    return {
        "status": "ok",
        "system_status": "ok" if healthy else "degraded",
        "services": services,
    }


@public_router.post("/auth/token", response_model=TokenResponse)
async def login(body: TokenRequest):
    """Exchange API key for a JWT access token."""
    if body.api_key != settings.api_secret_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    token = create_access_token()
    return TokenResponse(access_token=token)


@public_router.get("/contract", response_model=ApiContractResponse)
async def contract_metadata():
    """Public API contract metadata for independent clients."""
    return ApiContractResponse(
        rest_base="/api",
        websocket_base="/api/ws",
        auth_token_path="/api/auth/token",
        websocket_auth="query_param_token",
        public_routes=[
            "/api/health",
            "/api/auth/token",
            "/api/contract",
        ],
        protected_routes=[
            "/api/health/broker",
            "/api/health/system",
            "/api/universe",
            "/api/trades",
            "/api/signals",
            "/api/state-machine",
            "/api/portfolio",
            "/api/breakouts",
            "/api/secret-sauce/contract",
            "/api/secret-sauce/handoffs",
            "/api/secret-sauce/queue",
            "/api/secret-sauce/status",
            "/api/secret-sauce/replay",
            "/api/ml/status",
            "/api/ml/retrain",
            "/api/ml/backtest",
            "/api/analytics/kpis",
            "/api/analytics/signal-accuracy",
        ],
        websocket_channels=[
            "/api/ws",
            "/api/ws/l1",
            "/api/ws/l2",
            "/api/ws/signals",
            "/api/ws/trades",
        ],
    )


# ── Protected routes (require JWT) ───────────────────────────────────

router = APIRouter(dependencies=[Depends(require_auth)])


@router.get("/health/broker")
async def broker_health(broker=Depends(get_broker)):
    """Report IB Gateway / broker connection status."""
    return {
        "broker_type": settings.broker_type,
        "connected": broker.is_connected(),
        "host": settings.ibkr_host if settings.broker_type == "ibkr" else None,
        "port": settings.ibkr_port if settings.broker_type == "ibkr" else None,
    }


@router.get("/universe", response_model=list[SymbolRead])
def get_universe(active_only: bool = True, db: Session = Depends(get_db)):
    """Get all symbols in the universe."""
    query = db.query(Symbol)
    if active_only:
        query = query.filter_by(is_active=True)
    return query.order_by(Symbol.ticker).all()


@router.get("/trades", response_model=list[TradeRead])
def get_trades(limit: int = 50, db: Session = Depends(get_db)):
    """Get recent trades."""
    return db.query(Trade).order_by(Trade.created_at.desc()).limit(limit).all()


@router.get("/signals", response_model=list[SignalRead])
def get_signals(limit: int = 50, db: Session = Depends(get_db)):
    """Get recent signals."""
    return db.query(Signal).order_by(Signal.created_at.desc()).limit(limit).all()


@router.get("/state-machine")
async def get_state_machine_status(sm=Depends(get_state_machine)):
    """Get current state machine status for all tracked tickers."""
    if sm is None:
        return []
    return [
        {
            "ticker": s.ticker,
            "stage": s.stage.value,
            "score": round(s.score, 4),
            "entered_at": s.entered_at.isoformat(),
            "consecutive_ticks": s.consecutive_ticks,
            "decay_ticks": s.decay_ticks,
            "reason": s.reason,
        }
        for s in sm.all_states()
        if s.stage.value != "normal"
    ]


@router.get("/portfolio")
async def get_portfolio(broker=Depends(get_broker)):
    """Get current portfolio — delegates to the active broker instance."""
    if not broker.is_connected():
        return {
            "cash_balance": 0.0,
            "total_value": 0.0,
            "buying_power": 0.0,
            "positions": [],
            "daily_pnl": 0.0,
        }
    summary = await broker.get_account_summary()
    return asdict(summary)


@router.get("/health/system")
async def system_health(runtime=Depends(get_runtime)):
    """Detailed orchestration health including background worker state."""
    return runtime.snapshot()


# ── Breakout Engine Endpoints ─────────────────────────────────────────


@router.get("/breakouts")
async def get_breakout_candidates(request: Request):
    """Get current L1 breakout candidates from the breakout engine."""
    engine = getattr(request.app.state, "breakout_engine", None)
    if engine is None:
        return []
    events = engine.scan()
    return [
        {
            "ticker": e.ticker,
            "breakout_score": e.breakout_score,
            "pct_change_1m": e.pct_change_1m,
            "pct_change_5m": e.pct_change_5m,
            "volume_ratio": e.volume_ratio,
            "timestamp": e.timestamp.isoformat(),
        }
        for e in events
    ]


@router.get("/secret-sauce/contract", response_model=SecretSauceContractResponse)
async def get_secret_sauce_contract():
    return SecretSauceContractResponse(
        consumer="secret_sauce",
        handoff_route="/api/secret-sauce/handoffs",
        handoff_fields=[
            "ticker",
            "score",
            "detected_at",
            "price_velocity_1m",
            "volume_expansion",
            "spread_pct",
            "quote_rate",
            "buy_pressure",
            "reason_flags",
            "promotion_reason",
            "consumer",
            "l2_required",
        ],
        promotion_reason="secret_candidate",
        requires_l2=True,
    )


@router.get("/secret-sauce/handoffs", response_model=list[SecretSauceHandoffResponse])
async def get_secret_sauce_handoffs(request: Request, limit: int = 50):
    manager = getattr(request.app.state, "secret_sauce_handoffs", None)
    if manager is None:
        return []
    return [SecretSauceHandoffResponse(**handoff.to_dict()) for handoff in manager.recent(limit)]


@router.get("/secret-sauce/queue", response_model=SecretSauceQueueStatusResponse)
async def get_secret_sauce_queue_status(request: Request):
    manager = getattr(request.app.state, "secret_l2_promotion_queue", None)
    if manager is None:
        return SecretSauceQueueStatusResponse(
            active_count=0,
            active_tickers=[],
            queue_depth=0,
            queued_tickers=[],
            max_active=0,
            max_queue_size=0,
        )
    return SecretSauceQueueStatusResponse(**manager.snapshot())


@router.get("/secret-sauce/status", response_model=SecretSauceStatusResponse)
async def get_secret_sauce_status(request: Request):
    queue = getattr(request.app.state, "secret_l2_promotion_queue", None)
    runtime = getattr(request.app.state, "secret_runtime_status", None)
    polygon_client = getattr(request.app.state, "polygon_client", None)
    queue_snapshot = (
        queue.snapshot()
        if queue is not None
        else {
            "active_count": 0,
            "active_tickers": [],
            "queue_depth": 0,
            "queued_tickers": [],
            "max_active": 0,
            "max_queue_size": 0,
            "replaceable_tickers": [],
        }
    )
    runtime_snapshot = runtime.to_dict() if runtime is not None else {}
    polygon_snapshot = polygon_client.session_snapshot() if polygon_client is not None else None
    return SecretSauceStatusResponse(
        runtime=runtime_snapshot,
        queue=SecretSauceQueueStatusResponse(**queue_snapshot),
        polygon_session=polygon_snapshot,
    )


@router.post("/secret-sauce/replay", response_model=SecretReplayResponse)
async def replay_secret_sauce(body: SecretReplayRequest):
    validator = SecretReplayValidator(
        scorer=SecretCandidateScorer(
            min_score=settings.secret_candidate_min_score,
            max_spread_pct=settings.secret_candidate_max_spread_pct,
            min_quote_rate=settings.secret_candidate_min_quote_rate,
            min_buy_pressure=settings.secret_candidate_min_buy_pressure,
            min_volume_expansion=settings.secret_candidate_min_volume_expansion,
        ),
        max_active=settings.secret_l2_max_active,
        max_queue_size=settings.secret_l2_queue_maxsize,
    )
    result = await validator.run(
        [
            build_replay_quote(
                ticker=quote.ticker,
                bid=quote.bid,
                ask=quote.ask,
                last=quote.last,
                volume=quote.volume,
                timestamp=quote.timestamp,
            )
            for quote in body.quotes
        ]
    )
    return SecretReplayResponse(
        snapshots=result.snapshots,
        candidates=result.candidates,
        handoffs=result.handoffs,
        queue=SecretSauceQueueStatusResponse(**result.queue),
        promoted_tickers=result.promoted_tickers,
    )


# ── ML Endpoints ─────────────────────────────────────────────────────


@router.get("/ml/status", response_model=MLStatusResponse)
async def ml_status(request: Request):
    """Get ML model status and configuration."""
    classifier = getattr(request.app.state, "classifier", None)
    return MLStatusResponse(
        model_trained=classifier.is_trained if classifier else False,
        feature_importances=classifier.feature_importances() if classifier and classifier.is_trained else None,
        ml_enabled=settings.ml_enabled,
        ml_confidence_weight=settings.ml_confidence_weight,
        min_training_samples=settings.ml_min_training_samples,
    )


@router.post("/ml/retrain", response_model=RetrainResponse)
async def ml_retrain(request: Request):
    """Trigger manual model retraining."""
    trainer = getattr(request.app.state, "trainer", None)
    if trainer is None:
        return RetrainResponse(status="error")

    metrics = await trainer.retrain_if_needed()
    if metrics is None:
        return RetrainResponse(status="insufficient_data")

    return RetrainResponse(status="retrained", samples=metrics.get("samples"), metrics=metrics)


@router.post("/ml/backtest", response_model=BacktestResponse)
def ml_backtest(body: BacktestRequest, db: Session = Depends(get_db)):
    """Run a signal-replay backtest."""
    config = BacktestConfig(
        start_date=body.start_date,
        end_date=body.end_date,
        slippage_pct=body.slippage_pct,
        commission_per_share=body.commission_per_share,
        initial_capital=body.initial_capital,
        max_position_size=body.max_position_size,
        score_threshold=body.score_threshold,
    )
    result = SignalBacktester(db, config).run()
    return BacktestResponse(
        total_trades=result.total_trades,
        winning_trades=result.winning_trades,
        losing_trades=result.losing_trades,
        total_pnl=result.total_pnl,
        win_rate=result.win_rate,
        avg_win=result.avg_win,
        avg_loss=result.avg_loss,
        profit_factor=result.profit_factor,
        max_drawdown=result.max_drawdown,
        sharpe_ratio=result.sharpe_ratio,
        trades=result.trades,
    )


# ── Analytics Endpoints ──────────────────────────────────────────────


@router.get("/analytics/kpis", response_model=KPIResponse)
def analytics_kpis(days: int = 30, db: Session = Depends(get_db)):
    """Get trading KPIs for the last N days."""
    return TradeAnalytics(db).compute_kpis(days=days)


@router.get("/analytics/signal-accuracy", response_model=list[SignalAccuracyBucketResponse])
def analytics_signal_accuracy(db: Session = Depends(get_db)):
    """Get win rate by signal score bucket."""
    return TradeAnalytics(db).signal_accuracy_by_bucket()
