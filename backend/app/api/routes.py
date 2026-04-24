"""REST API routes for Stock Radar System."""

from collections import Counter
from dataclasses import asdict
from datetime import date, datetime, time as dt_time, timedelta, timezone
from statistics import median

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import and_, func, or_, text
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
from app.api.observability import track_tables
from app.ml.analytics import TradeAnalytics
from app.ml.backtest import BacktestConfig, SignalBacktester
from app.engine.secret_candidate_scorer import SecretCandidateScorer
from app.engine.secret_replay_validator import SecretReplayValidator, build_replay_quote
from app.models.l1_candidate import L1Candidate
from app.models.l1_to_l2_event import L1ToL2Event
from app.models.candidate_event import CandidateEvent
from app.models.decision_event import DecisionEvent
from app.models.polygon_day_aggregate import PolygonDayAggregate
from app.models.polygon_minute_aggregate import PolygonMinuteAggregate
from app.models.polygon_minute_aggregate_live import PolygonMinuteAggregateLive
from app.models.polygon_second_aggregate import PolygonSecondAggregate
from app.models.polygon_second_aggregate_live import PolygonSecondAggregateLive
from app.models.polygon_tick import PolygonTick
from app.models.polygon_tick_live import PolygonTickLive
from app.models.signal import Signal
from app.models.symbol import Symbol
from app.models.symbol_state_live import SymbolStateLive
from app.models.trade import Trade
from app.models.universe_daily import UniverseDaily
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
    SecretUniverseDailyResponse,
    SecretL1CandidateResponse,
    SecretL1ToL2EventResponse,
    SecretSauceFunnelResponse,
    SecretSauceLatencySummaryResponse,
    SecretSauceReasonCountResponse,
    PolygonDayAggregateResponse,
    PolygonDayAggregatePageResponse,
    PolygonMinuteAggregateResponse,
    PolygonMinuteAggregatePageResponse,
    PolygonSecondAggregateResponse,
    PolygonSecondAggregatePageResponse,
    PolygonTickResponse,
    PolygonTickPageResponse,
    SymbolStateLiveResponse,
    SymbolStateLivePageResponse,
    CandidateEventResponse,
    CandidateEventPageResponse,
    DecisionEventResponse,
    DecisionEventPageResponse,
    L2HealthResponse,
    L2SubscriptionStatusResponse,
    SecretReplayRequest,
    SecretReplayResponse,
    SignalAccuracyBucketResponse,
)
from app.schemas.signal import SignalRead
from app.schemas.symbol import SymbolRead
from app.schemas.trade import TradeRead

# ── Public routes (no auth) ──────────────────────────────────────────

public_router = APIRouter()


@public_router.get("/health/live")
async def health_live():
    return {"status": "ok"}


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
            "/api/health/live",
            "/api/health",
            "/api/auth/token",
            "/api/contract",
        ],
        protected_routes=[
            "/api/health/broker",
            "/api/health/l2",
            "/api/health/system",
            "/api/universe",
            "/api/trades",
            "/api/signals",
            "/api/state-machine",
            "/api/portfolio",
            "/api/breakouts",
            "/api/polygon/day-aggregates",
            "/api/polygon/minute-aggregates",
            "/api/polygon/second-aggregates",
            "/api/polygon/ticks",
            "/api/secret-sauce/contract",
            "/api/secret-sauce/handoffs",
            "/api/secret-sauce/queue",
            "/api/secret-sauce/status",
            "/api/secret-sauce/replay",
            "/api/secret-sauce/universe-daily",
            "/api/secret-sauce/l1-candidates",
            "/api/secret-sauce/l1-to-l2-events",
            "/api/secret-sauce/funnel",
            "/api/polygon/day-aggregates",
            "/api/polygon/minute-aggregates",
            "/api/polygon/ticks",
            "/api/ml/status",
            "/api/ml/retrain",
            "/api/ml/backtest",
            "/api/analytics/kpis",
            "/api/analytics/signal-accuracy",
            "/api/aggregate/symbol-state-live",
            "/api/aggregate/candidate-events",
            "/api/aggregate/decision-events",
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


def _latest_universe_tickers(
    db: Session,
    *,
    max_price: float | None = None,
) -> list[str]:
    latest_trade_date = (
        db.query(UniverseDaily.trade_date)
        .order_by(UniverseDaily.trade_date.desc())
        .limit(1)
        .scalar()
    )
    if latest_trade_date is None:
        return []

    query = db.query(UniverseDaily).filter(UniverseDaily.trade_date == latest_trade_date)
    if max_price is not None:
        query = query.filter(func.coalesce(UniverseDaily.open_price, UniverseDaily.last_price, 0) <= max_price)
    rows = query.order_by(UniverseDaily.ticker.asc()).all()
    universe_tickers = [row.ticker for row in rows]
    if universe_tickers:
        return universe_tickers

    active_query = db.query(Symbol.ticker).filter(Symbol.is_active.is_(True))
    if max_price is not None:
        active_query = active_query.filter(func.coalesce(Symbol.last_price, 0) <= max_price)
    active_rows = active_query.order_by(Symbol.ticker.asc()).all()
    return [row.ticker for row in active_rows]


def _deduped_tick_query(db: Session, query, model):
    dedupe_subquery = (
        query.with_entities(
            model.ticker.label("ticker"),
            model.event_type.label("event_type"),
            model.bid.label("bid"),
            model.ask.label("ask"),
            model.last.label("last"),
            model.volume.label("volume"),
            model.tick_ts.label("tick_ts"),
            func.max(model.id).label("max_id"),
        )
        .group_by(
            model.ticker,
            model.event_type,
            model.bid,
            model.ask,
            model.last,
            model.volume,
            model.tick_ts,
        )
        .subquery()
    )
    return db.query(model).join(dedupe_subquery, model.id == dedupe_subquery.c.max_id)


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
@track_tables("symbols")
def get_universe(active_only: bool = True, db: Session = Depends(get_db)):
    """Get all symbols in the universe."""
    query = db.query(Symbol)
    if active_only:
        query = query.filter_by(is_active=True)
    return query.order_by(Symbol.ticker).all()


@router.get("/trades", response_model=list[TradeRead])
@track_tables("trades")
def get_trades(limit: int = 50, db: Session = Depends(get_db)):
    """Get recent trades."""
    return db.query(Trade).order_by(Trade.created_at.desc()).limit(limit).all()


@router.get("/signals", response_model=list[SignalRead])
@track_tables("signals")
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


@router.get("/health/l2", response_model=L2HealthResponse)
async def l2_health(request: Request):
    """Report runtime IBKR L2 subscription/depth status."""
    state_machine = getattr(request.app.state, "state_machine", None)
    if state_machine is None:
        return L2HealthResponse(
            active_count=0,
            books_with_depth_count=0,
            subscribed_tickers=[],
            subscriptions=[],
        )

    manager = getattr(state_machine, "l2_manager", None)
    if manager is None:
        return L2HealthResponse(
            active_count=0,
            books_with_depth_count=0,
            subscribed_tickers=[],
            subscriptions=[],
        )

    subscriptions: list[L2SubscriptionStatusResponse] = []
    books_with_depth_count = 0
    for ticker in sorted(manager.active_symbols):
        record = manager._active.get(ticker)  # noqa: SLF001 - runtime diagnostics
        order_book = None
        if record is not None:
            try:
                order_book = await manager.get_order_book(ticker)
            except Exception:
                order_book = None
        bid_levels = len(order_book.bids) if order_book is not None and order_book.bids else 0
        ask_levels = len(order_book.asks) if order_book is not None and order_book.asks else 0
        has_depth = bid_levels > 0 or ask_levels > 0
        if has_depth:
            books_with_depth_count += 1
        subscriptions.append(
            L2SubscriptionStatusResponse(
                ticker=ticker,
                confirmed=record.confirmed if record is not None else False,
                has_depth=has_depth,
                bid_levels=bid_levels,
                ask_levels=ask_levels,
                last_updated_at=record.last_updated_at if record is not None else None,
            )
        )

    return L2HealthResponse(
        active_count=len(manager.active_symbols),
        books_with_depth_count=books_with_depth_count,
        subscribed_tickers=sorted(manager.active_symbols),
        subscriptions=subscriptions,
    )


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
@track_tables("l1_to_l2_events")
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


@router.get("/secret-sauce/universe-daily", response_model=list[SecretUniverseDailyResponse])
@track_tables("universe_daily")
def get_secret_universe_daily(
    limit: int = 200,
    trade_date: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(UniverseDaily)
    if trade_date is None:
        latest_trade_date = (
            db.query(UniverseDaily.trade_date)
            .order_by(UniverseDaily.trade_date.desc())
            .limit(1)
            .scalar()
        )
        if latest_trade_date is None:
            return []
        query = query.filter(UniverseDaily.trade_date == latest_trade_date)
    else:
        query = query.filter(UniverseDaily.trade_date == trade_date)
    return (
        query.order_by(UniverseDaily.trade_date.desc(), UniverseDaily.ticker.asc())
        .limit(limit)
        .all()
    )


@router.get("/secret-sauce/l1-candidates", response_model=list[SecretL1CandidateResponse])
@track_tables("l1_candidates")
def get_secret_l1_candidates(limit: int = 100, db: Session = Depends(get_db)):
    return (
        db.query(L1Candidate)
        .order_by(L1Candidate.detected_at.desc(), L1Candidate.id.desc())
        .limit(limit)
        .all()
    )


@router.get("/secret-sauce/l1-to-l2-events", response_model=list[SecretL1ToL2EventResponse])
@track_tables("l1_to_l2_events")
def get_secret_l1_to_l2_events(limit: int = 100, db: Session = Depends(get_db)):
    return (
        db.query(L1ToL2Event)
        .order_by(L1ToL2Event.escalate_ts.desc(), L1ToL2Event.id.desc())
        .limit(limit)
        .all()
    )


@router.get("/secret-sauce/funnel", response_model=SecretSauceFunnelResponse)
@track_tables("universe_daily", "l1_candidates", "l1_to_l2_events")
def get_secret_sauce_funnel(
    trade_date: str | None = None,
    db: Session = Depends(get_db),
):
    selected_trade_date: date | None = None
    if trade_date is None:
        selected_trade_date = (
            db.query(UniverseDaily.trade_date)
            .order_by(UniverseDaily.trade_date.desc())
            .limit(1)
            .scalar()
        )
    else:
        try:
            selected_trade_date = date.fromisoformat(trade_date)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid trade_date") from exc

    if selected_trade_date is None:
        empty_latency = SecretSauceLatencySummaryResponse(count=0)
        return SecretSauceFunnelResponse(
            trade_date=None,
            universe_count=0,
            candidate_count=0,
            handoff_count=0,
            candidate_conversion_pct=0.0,
            handoff_conversion_pct=0.0,
            universe_to_handoff_pct=0.0,
            latency=empty_latency,
            top_reason_flags=[],
            top_escalation_reasons=[],
        )

    start_dt = datetime.combine(selected_trade_date, datetime.min.time(), tzinfo=timezone.utc).replace(tzinfo=None)
    end_dt = start_dt + timedelta(days=1)

    universe_rows = (
        db.query(UniverseDaily)
        .filter(UniverseDaily.trade_date == selected_trade_date)
        .all()
    )
    candidate_rows = (
        db.query(L1Candidate)
        .filter(L1Candidate.detected_at >= start_dt)
        .filter(L1Candidate.detected_at < end_dt)
        .all()
    )
    handoff_rows = (
        db.query(L1ToL2Event)
        .filter(L1ToL2Event.escalate_ts >= start_dt)
        .filter(L1ToL2Event.escalate_ts < end_dt)
        .all()
    )

    universe_tickers = {row.ticker for row in universe_rows}
    candidate_tickers = {row.ticker for row in candidate_rows}
    handoff_tickers = {row.ticker for row in handoff_rows}

    universe_count = len(universe_tickers)
    candidate_count = len(candidate_tickers & universe_tickers) if universe_tickers else len(candidate_tickers)
    handoff_count = len(handoff_tickers & candidate_tickers) if candidate_tickers else len(handoff_tickers)

    latency_values = [row.latency_ms for row in handoff_rows if row.latency_ms is not None]
    latency_values.sort()
    latency_summary = SecretSauceLatencySummaryResponse(
        count=len(latency_values),
        avg_ms=(sum(latency_values) / len(latency_values)) if latency_values else None,
        median_ms=median(latency_values) if latency_values else None,
        p95_ms=(latency_values[min(len(latency_values) - 1, int(len(latency_values) * 0.95))] if latency_values else None),
    )

    reason_counter: Counter[str] = Counter()
    for row in candidate_rows:
        if not row.reason_flags:
            continue
        for flag in (part.strip() for part in row.reason_flags.split(",") if part.strip()):
            reason_counter[flag] += 1

    escalation_counter: Counter[str] = Counter(
        row.escalation_reason for row in handoff_rows if row.escalation_reason
    )

    top_reason_flags = [
        SecretSauceReasonCountResponse(label=label, count=count)
        for label, count in reason_counter.most_common(5)
    ]
    top_escalation_reasons = [
        SecretSauceReasonCountResponse(label=label, count=count)
        for label, count in escalation_counter.most_common(5)
    ]

    return SecretSauceFunnelResponse(
        trade_date=selected_trade_date,
        universe_count=universe_count,
        candidate_count=candidate_count,
        handoff_count=handoff_count,
        candidate_conversion_pct=(candidate_count / universe_count * 100.0) if universe_count else 0.0,
        handoff_conversion_pct=(handoff_count / candidate_count * 100.0) if candidate_count else 0.0,
        universe_to_handoff_pct=(handoff_count / universe_count * 100.0) if universe_count else 0.0,
        latency=latency_summary,
        top_reason_flags=top_reason_flags,
        top_escalation_reasons=top_escalation_reasons,
    )


@router.get("/polygon/day-aggregates", response_model=PolygonDayAggregatePageResponse)
@track_tables("polygon_day_aggregates")
def get_polygon_day_aggregates(
    page: int = 0,
    page_size: int = 25,
    trade_date: date | None = None,
    ticker: str | None = None,
    universe_only: bool = True,
    db: Session = Depends(get_db),
):
    query = db.query(PolygonDayAggregate)
    selected_trade_date: date | None = trade_date
    if trade_date is None:
        latest_trade_date = (
            db.query(PolygonDayAggregate.trade_date)
            .order_by(PolygonDayAggregate.trade_date.desc())
            .limit(1)
            .scalar()
        )
        if latest_trade_date is None:
            return PolygonDayAggregatePageResponse(items=[], total=0, page=page, page_size=page_size, trade_date=None)
        selected_trade_date = latest_trade_date
        query = query.filter(PolygonDayAggregate.trade_date == latest_trade_date)
    else:
        query = query.filter(PolygonDayAggregate.trade_date == trade_date)
    if universe_only:
        universe_tickers = _latest_universe_tickers(db, max_price=settings.secret_universe_max_price)
        if not universe_tickers:
            return PolygonDayAggregatePageResponse(
                items=[],
                total=0,
                page=page,
                page_size=page_size,
                trade_date=selected_trade_date,
            )
        query = query.filter(PolygonDayAggregate.ticker.in_(universe_tickers))
    if ticker:
        query = query.filter(PolygonDayAggregate.ticker == ticker.upper())
    total = query.count()
    rows = (
        query.order_by(PolygonDayAggregate.trade_date.desc(), PolygonDayAggregate.ticker.asc())
        .offset(page * page_size)
        .limit(page_size)
        .all()
    )
    return PolygonDayAggregatePageResponse(
        items=[PolygonDayAggregateResponse.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        trade_date=selected_trade_date,
    )


@router.get("/polygon/minute-aggregates", response_model=PolygonMinuteAggregatePageResponse)
@track_tables("minute_aggregates_live")
def get_polygon_minute_aggregates(
    page: int = 0,
    page_size: int = 25,
    trade_date: date | None = None,
    ticker: str | None = None,
    session_start_et: dt_time | None = None,
    session_time_et: dt_time | None = None,
    universe_only: bool = True,
    db: Session = Depends(get_db),
):
    query = db.query(PolygonMinuteAggregateLive)
    selected_trade_date = trade_date
    if selected_trade_date is None:
        latest_minute_ts = db.query(func.max(PolygonMinuteAggregateLive.minute_ts)).scalar()
        if latest_minute_ts is not None:
            selected_trade_date = latest_minute_ts.date()
    if universe_only:
        universe_tickers = _latest_universe_tickers(db, max_price=settings.secret_universe_max_price)
        if not universe_tickers:
            return PolygonMinuteAggregatePageResponse(
                items=[],
                total=0,
                page=page,
                page_size=page_size,
                trade_date=selected_trade_date,
            )
        query = query.filter(PolygonMinuteAggregateLive.ticker.in_(universe_tickers))
    if selected_trade_date:
        start_dt = datetime.combine(selected_trade_date, datetime.min.time())
        end_dt = start_dt + timedelta(days=1)
        query = query.filter(
            PolygonMinuteAggregateLive.minute_ts >= start_dt,
            PolygonMinuteAggregateLive.minute_ts < end_dt,
        )
    requested_session_start = session_start_et or session_time_et
    if requested_session_start is not None:
        query = query.filter(
            text(
                "timezone('America/New_York', minute_ts at time zone 'UTC')::time >= CAST(:session_start_et AS time)"
            ).bindparams(session_start_et=requested_session_start)
        )
    if ticker:
        query = query.filter(PolygonMinuteAggregateLive.ticker == ticker.upper())
    total = query.count()
    rows = (
        query.order_by(PolygonMinuteAggregateLive.minute_ts.desc(), PolygonMinuteAggregateLive.id.desc())
        .offset(page * page_size)
        .limit(page_size)
        .all()
    )
    return PolygonMinuteAggregatePageResponse(
        items=[PolygonMinuteAggregateResponse.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        trade_date=selected_trade_date,
    )


@router.get("/polygon/history/minute-aggregates", response_model=PolygonMinuteAggregatePageResponse)
@track_tables("polygon_minute_aggregates")
def get_polygon_minute_aggregates_history(
    page: int = 0,
    page_size: int = 25,
    trade_date: date | None = None,
    ticker: str | None = None,
    universe_only: bool = True,
    db: Session = Depends(get_db),
):
    query = db.query(PolygonMinuteAggregate)
    selected_trade_date = trade_date
    if selected_trade_date is None:
        latest_minute_ts = db.query(func.max(PolygonMinuteAggregate.minute_ts)).scalar()
        if latest_minute_ts is not None:
            selected_trade_date = latest_minute_ts.date()
    if universe_only:
        universe_tickers = _latest_universe_tickers(db, max_price=settings.secret_universe_max_price)
        if not universe_tickers:
            return PolygonMinuteAggregatePageResponse(
                items=[],
                total=0,
                page=page,
                page_size=page_size,
                trade_date=selected_trade_date,
            )
        query = query.filter(PolygonMinuteAggregate.ticker.in_(universe_tickers))
    if selected_trade_date is not None:
        start_dt = datetime.combine(selected_trade_date, datetime.min.time())
        end_dt = start_dt + timedelta(days=1)
        query = query.filter(PolygonMinuteAggregate.minute_ts >= start_dt, PolygonMinuteAggregate.minute_ts < end_dt)
    if ticker:
        query = query.filter(PolygonMinuteAggregate.ticker == ticker.upper())
    total = query.count()
    rows = (
        query.order_by(PolygonMinuteAggregate.minute_ts.desc(), PolygonMinuteAggregate.id.desc())
        .offset(page * page_size)
        .limit(page_size)
        .all()
    )
    return PolygonMinuteAggregatePageResponse(
        items=[PolygonMinuteAggregateResponse.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        trade_date=selected_trade_date,
    )


@router.get("/polygon/second-aggregates", response_model=PolygonSecondAggregatePageResponse)
@track_tables("polygon_second_aggregates_live")
def get_polygon_second_aggregates(
    page: int = 0,
    page_size: int = 25,
    trade_date: date | None = None,
    ticker: str | None = None,
    event_type: str | None = "trade",
    session_start_et: dt_time | None = None,
    session_time_et: dt_time | None = None,
    universe_only: bool = True,
    db: Session = Depends(get_db),
):
    query = db.query(PolygonSecondAggregateLive)
    selected_trade_date = trade_date
    if selected_trade_date is None:
        latest_second_ts = db.query(func.max(PolygonSecondAggregateLive.second_ts)).scalar()
        if latest_second_ts is not None:
            selected_trade_date = latest_second_ts.date()
    if universe_only:
        universe_tickers = _latest_universe_tickers(db, max_price=settings.secret_universe_max_price)
        if not universe_tickers:
            return PolygonSecondAggregatePageResponse(
                items=[],
                total=0,
                page=page,
                page_size=page_size,
                trade_date=selected_trade_date,
            )
        query = query.filter(PolygonSecondAggregateLive.ticker.in_(universe_tickers))
    if selected_trade_date is not None:
        start_dt = datetime.combine(selected_trade_date, datetime.min.time())
        end_dt = start_dt + timedelta(days=1)
        query = query.filter(PolygonSecondAggregateLive.second_ts >= start_dt, PolygonSecondAggregateLive.second_ts < end_dt)
    requested_session_start = session_start_et or session_time_et
    if requested_session_start is not None:
        query = query.filter(
            text(
                "timezone('America/New_York', second_ts at time zone 'UTC')::time >= CAST(:session_start_et AS time)"
            ).bindparams(session_start_et=requested_session_start)
        )
    if ticker:
        query = query.filter(PolygonSecondAggregateLive.ticker == ticker.upper())
    total = query.count()
    rows = (
        query.order_by(PolygonSecondAggregateLive.second_ts.desc(), PolygonSecondAggregateLive.ticker.asc())
        .offset(page * page_size)
        .limit(page_size)
        .all()
    )
    return PolygonSecondAggregatePageResponse(
        items=[PolygonSecondAggregateResponse.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        trade_date=selected_trade_date,
    )


@router.get("/polygon/history/second-aggregates", response_model=PolygonSecondAggregatePageResponse)
@track_tables("polygon_second_aggregates")
def get_polygon_second_aggregates_history(
    page: int = 0,
    page_size: int = 25,
    trade_date: date | None = None,
    ticker: str | None = None,
    universe_only: bool = True,
    db: Session = Depends(get_db),
):
    query = db.query(PolygonSecondAggregate)
    selected_trade_date = trade_date
    if selected_trade_date is None:
        latest_second_ts = db.query(func.max(PolygonSecondAggregate.second_ts)).scalar()
        if latest_second_ts is not None:
            selected_trade_date = latest_second_ts.date()
    if universe_only:
        universe_tickers = _latest_universe_tickers(db, max_price=settings.secret_universe_max_price)
        if not universe_tickers:
            return PolygonSecondAggregatePageResponse(
                items=[],
                total=0,
                page=page,
                page_size=page_size,
                trade_date=selected_trade_date,
            )
        query = query.filter(PolygonSecondAggregate.ticker.in_(universe_tickers))
    if selected_trade_date is not None:
        start_dt = datetime.combine(selected_trade_date, datetime.min.time())
        end_dt = start_dt + timedelta(days=1)
        query = query.filter(PolygonSecondAggregate.second_ts >= start_dt, PolygonSecondAggregate.second_ts < end_dt)
    if ticker:
        query = query.filter(PolygonSecondAggregate.ticker == ticker.upper())
    total = query.count()
    rows = (
        query.order_by(PolygonSecondAggregate.second_ts.desc(), PolygonSecondAggregate.ticker.asc())
        .offset(page * page_size)
        .limit(page_size)
        .all()
    )
    return PolygonSecondAggregatePageResponse(
        items=[PolygonSecondAggregateResponse.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        trade_date=selected_trade_date,
    )


@router.get("/polygon/ticks", response_model=PolygonTickPageResponse)
@track_tables("polygon_ticks_live")
def get_polygon_ticks(
    page: int = 0,
    page_size: int = 25,
    cursor: str | None = None,
    trade_date: date | None = None,
    ticker: str | None = None,
    event_type: str | None = None,
    universe_only: bool = True,
    db: Session = Depends(get_db),
):
    query = db.query(PolygonTickLive)
    selected_trade_date = trade_date
    normalized_ticker = ticker.upper() if ticker else None
    if selected_trade_date is None:
        latest_tick_ts = db.query(func.max(PolygonTickLive.tick_ts)).scalar()
        if latest_tick_ts is not None:
            selected_trade_date = latest_tick_ts.date()
    if universe_only:
        universe_tickers = _latest_universe_tickers(db, max_price=settings.secret_universe_max_price)
        if not universe_tickers:
            return PolygonTickPageResponse(
                items=[],
                page_size=page_size,
                trade_date=selected_trade_date,
                next_cursor=None,
                has_more=False,
            )
        query = query.filter(PolygonTickLive.ticker.in_(universe_tickers))
    if selected_trade_date:
        start_dt = datetime.combine(selected_trade_date, datetime.min.time())
        end_dt = start_dt + timedelta(days=1)
        query = query.filter(PolygonTickLive.tick_ts >= start_dt, PolygonTickLive.tick_ts < end_dt)
    if normalized_ticker:
        query = query.filter(PolygonTickLive.ticker == normalized_ticker)
    if event_type:
        query = query.filter(PolygonTickLive.event_type == event_type.lower())
    query = _deduped_tick_query(db, query, PolygonTickLive)
    total = query.count()
    if cursor:
        try:
            cursor_ts_raw, cursor_id_raw = cursor.rsplit("|", 1)
            cursor_ts = datetime.fromisoformat(cursor_ts_raw)
            cursor_id = int(cursor_id_raw)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tick cursor") from exc
        query = query.filter(
            or_(
                PolygonTickLive.tick_ts < cursor_ts,
                and_(PolygonTickLive.tick_ts == cursor_ts, PolygonTickLive.id < cursor_id),
            )
        )
    rows = (
        query.order_by(PolygonTickLive.tick_ts.desc(), PolygonTickLive.id.desc())
        .limit(page_size + 1)
        .all()
    )
    has_more = len(rows) > page_size
    visible_rows = rows[:page_size]
    next_cursor = None
    if has_more and visible_rows:
        last_row = visible_rows[-1]
        next_cursor = f"{last_row.tick_ts.isoformat()}|{last_row.id}"
    return PolygonTickPageResponse(
        items=[PolygonTickResponse.model_validate(row) for row in visible_rows],
        total=total,
        page_size=page_size,
        trade_date=selected_trade_date,
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.get("/polygon/history/ticks", response_model=PolygonTickPageResponse)
@track_tables("polygon_ticks")
def get_polygon_ticks_history(
    page: int = 0,
    page_size: int = 25,
    trade_date: date | None = None,
    ticker: str | None = None,
    event_type: str | None = None,
    universe_only: bool = True,
    db: Session = Depends(get_db),
):
    query = db.query(PolygonTick)
    selected_trade_date = trade_date
    normalized_ticker = ticker.upper() if ticker else None
    if selected_trade_date is None:
        latest_tick_ts = db.query(func.max(PolygonTick.tick_ts)).scalar()
        if latest_tick_ts is not None:
            selected_trade_date = latest_tick_ts.date()
    if universe_only:
        universe_tickers = _latest_universe_tickers(db, max_price=settings.secret_universe_max_price)
        if not universe_tickers:
            return PolygonTickPageResponse(
                items=[],
                total=0,
                page=page,
                page_size=page_size,
                trade_date=selected_trade_date,
            )
        query = query.filter(PolygonTick.ticker.in_(universe_tickers))
    if selected_trade_date:
        start_dt = datetime.combine(selected_trade_date, datetime.min.time())
        end_dt = start_dt + timedelta(days=1)
        query = query.filter(PolygonTick.tick_ts >= start_dt, PolygonTick.tick_ts < end_dt)
    if normalized_ticker:
        query = query.filter(PolygonTick.ticker == normalized_ticker)
    if event_type:
        query = query.filter(PolygonTick.event_type == event_type.lower())
    query = _deduped_tick_query(db, query, PolygonTick)
    total = query.count()
    rows = (
        query.order_by(PolygonTick.tick_ts.desc(), PolygonTick.id.desc())
        .offset(page * page_size)
        .limit(page_size)
        .all()
    )
    return PolygonTickPageResponse(
        items=[PolygonTickResponse.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        trade_date=selected_trade_date,
    )


@router.get("/aggregate/symbol-state-live", response_model=SymbolStateLivePageResponse)
@track_tables("symbol_state_live")
def get_symbol_state_live(
    page: int = 0,
    page_size: int = 25,
    ticker: str | None = None,
    candidate_status: str | None = None,
    universe_only: bool = True,
    db: Session = Depends(get_db),
):
    query = db.query(SymbolStateLive)
    if universe_only:
        universe_tickers = _latest_universe_tickers(db, max_price=settings.secret_universe_max_price)
        if not universe_tickers:
            return SymbolStateLivePageResponse(items=[], total=0, page=page, page_size=page_size, summary={})
        query = query.filter(SymbolStateLive.ticker.in_(universe_tickers))
    if ticker:
        query = query.filter(SymbolStateLive.ticker == ticker.upper())
    if candidate_status:
        query = query.filter(SymbolStateLive.candidate_status == candidate_status.lower())
    total = query.count()
    status_counts = {
        status or "unknown": count
        for status, count in query.with_entities(SymbolStateLive.candidate_status, func.count())
        .group_by(SymbolStateLive.candidate_status)
        .all()
    }
    stale_count = query.filter(
        or_(SymbolStateLive.is_second_stream_stale.is_(True), SymbolStateLive.is_minute_stream_stale.is_(True))
    ).count()
    summary = {
        **status_counts,
        "stale": stale_count,
    }
    rows = (
        query.order_by(
            SymbolStateLive.updated_at.desc().nullslast(),
            SymbolStateLive.ticker.asc(),
        )
        .offset(page * page_size)
        .limit(page_size)
        .all()
    )
    return SymbolStateLivePageResponse(
        items=[SymbolStateLiveResponse.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        summary=summary,
    )


@router.get("/aggregate/candidate-events", response_model=CandidateEventPageResponse)
@track_tables("candidate_events")
def get_candidate_events(
    page: int = 0,
    page_size: int = 25,
    trade_date: date | None = None,
    ticker: str | None = None,
    trigger_name: str | None = None,
    universe_only: bool = True,
    db: Session = Depends(get_db),
):
    query = db.query(CandidateEvent)
    selected_trade_date = trade_date
    if selected_trade_date is None:
        latest_event_ts = db.query(func.max(CandidateEvent.event_ts)).scalar()
        if latest_event_ts is not None:
            selected_trade_date = latest_event_ts.date()
    if universe_only:
        universe_tickers = _latest_universe_tickers(db, max_price=settings.secret_universe_max_price)
        if not universe_tickers:
            return CandidateEventPageResponse(
                items=[],
                total=0,
                page=page,
                page_size=page_size,
                trade_date=selected_trade_date,
                summary={},
            )
        query = query.filter(CandidateEvent.ticker.in_(universe_tickers))
    if selected_trade_date is not None:
        start_dt = datetime.combine(selected_trade_date, datetime.min.time())
        end_dt = start_dt + timedelta(days=1)
        query = query.filter(CandidateEvent.event_ts >= start_dt, CandidateEvent.event_ts < end_dt)
    if ticker:
        query = query.filter(CandidateEvent.ticker == ticker.upper())
    if trigger_name:
        query = query.filter(CandidateEvent.trigger_name == trigger_name)
    total = query.count()
    stale_count = query.filter(
        or_(CandidateEvent.is_second_stream_stale.is_(True), CandidateEvent.is_minute_stream_stale.is_(True))
    ).count()
    summary = {
        "events": total,
        "stale": stale_count,
        "live": total - stale_count,
    }
    rows = (
        query.order_by(CandidateEvent.event_ts.desc(), CandidateEvent.id.desc())
        .offset(page * page_size)
        .limit(page_size)
        .all()
    )
    return CandidateEventPageResponse(
        items=[CandidateEventResponse.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        trade_date=selected_trade_date,
        summary=summary,
    )


@router.get("/aggregate/decision-events", response_model=DecisionEventPageResponse)
@track_tables("decision_events")
def get_decision_events(
    page: int = 0,
    page_size: int = 25,
    trade_date: date | None = None,
    ticker: str | None = None,
    decision_type: str | None = None,
    universe_only: bool = True,
    db: Session = Depends(get_db),
):
    query = db.query(DecisionEvent)
    selected_trade_date = trade_date
    if selected_trade_date is None:
        latest_decision_ts = db.query(func.max(DecisionEvent.decision_ts)).scalar()
        if latest_decision_ts is not None:
            selected_trade_date = latest_decision_ts.date()
    if universe_only:
        universe_tickers = _latest_universe_tickers(db, max_price=settings.secret_universe_max_price)
        if not universe_tickers:
            return DecisionEventPageResponse(
                items=[],
                total=0,
                page=page,
                page_size=page_size,
                trade_date=selected_trade_date,
                summary={},
            )
        query = query.filter(DecisionEvent.ticker.in_(universe_tickers))
    if selected_trade_date is not None:
        start_dt = datetime.combine(selected_trade_date, datetime.min.time())
        end_dt = start_dt + timedelta(days=1)
        query = query.filter(DecisionEvent.decision_ts >= start_dt, DecisionEvent.decision_ts < end_dt)
    if ticker:
        query = query.filter(DecisionEvent.ticker == ticker.upper())
    if decision_type:
        query = query.filter(DecisionEvent.decision_type == decision_type.lower())
    total = query.count()
    summary = {
        decision_type or "unknown": count
        for decision_type, count in query.with_entities(DecisionEvent.decision_type, func.count())
        .group_by(DecisionEvent.decision_type)
        .all()
    }
    rows = (
        query.order_by(DecisionEvent.decision_ts.desc(), DecisionEvent.id.desc())
        .offset(page * page_size)
        .limit(page_size)
        .all()
    )
    return DecisionEventPageResponse(
        items=[DecisionEventResponse.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        trade_date=selected_trade_date,
        summary=summary,
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
@track_tables("signals")
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
@track_tables("trades")
def analytics_kpis(days: int = 30, db: Session = Depends(get_db)):
    """Get trading KPIs for the last N days."""
    return TradeAnalytics(db).compute_kpis(days=days)


@router.get("/analytics/signal-accuracy", response_model=list[SignalAccuracyBucketResponse])
@track_tables("signals", "trades")
def analytics_signal_accuracy(db: Session = Depends(get_db)):
    """Get win rate by signal score bucket."""
    return TradeAnalytics(db).signal_accuracy_by_bucket()
