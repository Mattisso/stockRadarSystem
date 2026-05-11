"""REST API routes for Stock Radar System."""

from bisect import bisect_left
from collections import Counter
from contextlib import suppress
from dataclasses import asdict
import json
from datetime import date, datetime, time as dt_time, timedelta, timezone
from statistics import median
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
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
from app.core.logging import get_logger
from app.core.market_hours import REGULAR_MARKET_CLOSE, REGULAR_MARKET_OPEN
from app.api.dependencies import get_broker, get_runtime, get_state_machine
from app.api.observability import track_tables
from app.data.universe_loader import PolygonFlatFileUniverseLoader
from app.ml.analytics import TradeAnalytics
from app.ml.model_registry_service import ModelRegistryService
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
from app.models.universe_daily import (
    UNIVERSE_KIND_MARKET,
    UNIVERSE_SOURCE_BROKER_FILTER,
    UNIVERSE_SOURCE_LEGACY_MARKET_INFERRED,
    UNIVERSE_SOURCE_POLYGON_FLATFILE,
    UNIVERSE_SOURCE_POLYGON_GROUPED_DAY_REST,
    UniverseDaily,
)
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
    DecisionOutcomeDetailResponse,
    DecisionOutcomeSummaryResponse,
    DecisionOutcomeByReasonResponse,
    DuplicateBuyAuditResponse,
    SellToBuyChurnAuditResponse,
    DecisionMarketValidationRowResponse,
    DecisionMarketValidationPageResponse,
    DecisionRuntimeKpiResponse,
    L2HealthResponse,
    L2SubscriptionStatusResponse,
    SecretReplayRequest,
    SecretReplayResponse,
    SignalAccuracyBucketResponse,
)
from app.schemas.signal import SignalRead
from app.schemas.symbol import SymbolRead
from app.schemas.trade import TradeRead

log = get_logger(__name__)

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
            "/api/polygon/flatfiles/day-aggregates/download",
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
NEW_YORK_TZ = ZoneInfo("America/New_York")


def _market_universe_sources() -> tuple[str, ...]:
    if settings.secret_universe_source == "polygon":
        return (
            UNIVERSE_SOURCE_POLYGON_FLATFILE,
            UNIVERSE_SOURCE_POLYGON_GROUPED_DAY_REST,
            UNIVERSE_SOURCE_LEGACY_MARKET_INFERRED,
        )
    return (
        UNIVERSE_SOURCE_BROKER_FILTER,
        UNIVERSE_SOURCE_LEGACY_MARKET_INFERRED,
    )


def _universe_tickers_for_trade_date(
    db: Session,
    *,
    trade_date: date | None = None,
    max_price: float | None = None,
    allow_symbol_fallback: bool = True,
) -> list[str]:
    selected_trade_date = trade_date
    if selected_trade_date is None:
        selected_trade_date = (
            db.query(UniverseDaily.trade_date)
            .filter(UniverseDaily.universe_kind == UNIVERSE_KIND_MARKET)
            .filter(UniverseDaily.source.in_(_market_universe_sources()))
            .order_by(UniverseDaily.trade_date.desc())
            .limit(1)
            .scalar()
        )
    if selected_trade_date is None:
        return []

    query = (
        db.query(UniverseDaily)
        .filter(UniverseDaily.trade_date == selected_trade_date)
        .filter(UniverseDaily.universe_kind == UNIVERSE_KIND_MARKET)
        .filter(UniverseDaily.source.in_(_market_universe_sources()))
    )
    if max_price is not None:
        query = query.filter(func.coalesce(UniverseDaily.open_price, UniverseDaily.last_price, 0) <= max_price)
    rows = query.order_by(UniverseDaily.ticker.asc()).all()
    universe_tickers = [row.ticker for row in rows]
    if universe_tickers or not allow_symbol_fallback:
        return universe_tickers

    active_query = db.query(Symbol.ticker).filter(Symbol.is_active.is_(True))
    if max_price is not None:
        active_query = active_query.filter(func.coalesce(Symbol.last_price, 0) <= max_price)
    active_rows = active_query.order_by(Symbol.ticker.asc()).all()
    return [row.ticker for row in active_rows]


def _latest_universe_tickers(
    db: Session,
    *,
    max_price: float | None = None,
    allow_symbol_fallback: bool = True,
) -> list[str]:
    return _universe_tickers_for_trade_date(
        db,
        max_price=max_price,
        allow_symbol_fallback=allow_symbol_fallback,
    )


def _resolve_canonical_intraday_trade_date(
    db: Session,
    *,
    explicit_trade_date: date | None,
    model,
    ts_column,
) -> date | None:
    if explicit_trade_date is not None:
        return explicit_trade_date
    latest_ts = db.query(func.max(ts_column)).select_from(model).scalar()
    if latest_ts is None:
        return None
    return _intraday_trade_day(latest_ts)


def _source_latest_timestamp(
    db: Session,
    *,
    model,
    ts_column,
):
    return db.query(func.max(ts_column)).select_from(model).scalar()


def _intraday_trade_day(value: datetime) -> date:
    if value.tzinfo is None:
        aware = value.replace(tzinfo=timezone.utc)
    else:
        aware = value.astimezone(timezone.utc)
    return aware.astimezone(NEW_YORK_TZ).date()


def _intraday_trade_day_bounds(trade_date: date) -> tuple[datetime, datetime]:
    start_local = datetime.combine(trade_date, dt_time.min, tzinfo=NEW_YORK_TZ)
    end_local = start_local + timedelta(days=1)
    return (
        start_local.astimezone(timezone.utc).replace(tzinfo=None),
        end_local.astimezone(timezone.utc).replace(tzinfo=None),
    )


def _decision_trade_day(value: datetime) -> date:
    if value.tzinfo is None:
        aware = value.replace(tzinfo=timezone.utc)
    else:
        aware = value.astimezone(timezone.utc)
    return aware.astimezone(NEW_YORK_TZ).date()


def _default_decision_trade_day() -> date:
    return datetime.now(NEW_YORK_TZ).date()


def _decision_trade_day_bounds(trade_date: date) -> tuple[datetime, datetime]:
    start_local = datetime.combine(trade_date, dt_time.min, tzinfo=NEW_YORK_TZ)
    end_local = start_local + timedelta(days=1)
    return (
        start_local.astimezone(timezone.utc).replace(tzinfo=None),
        end_local.astimezone(timezone.utc).replace(tzinfo=None),
    )


def _session_bounds_for_trade_date(
    trade_date: date,
    *,
    session_start_et: dt_time,
    session_end_et: dt_time,
) -> tuple[datetime, datetime]:
    start_local = datetime.combine(trade_date, session_start_et, tzinfo=NEW_YORK_TZ)
    end_local = datetime.combine(trade_date, session_end_et, tzinfo=NEW_YORK_TZ)
    return (
        start_local.astimezone(timezone.utc).replace(tzinfo=None),
        end_local.astimezone(timezone.utc).replace(tzinfo=None),
    )


def _decision_trade_day_rows(db: Session, *, trade_date: date) -> list[DecisionEvent]:
    start_dt, end_dt = _decision_trade_day_bounds(trade_date)
    return (
        db.query(DecisionEvent)
        .filter(
            DecisionEvent.decision_type.in_(("buy", "sell")),
            DecisionEvent.decision_ts >= start_dt,
            DecisionEvent.decision_ts < end_dt,
        )
        .order_by(DecisionEvent.ticker.asc(), DecisionEvent.decision_ts.asc(), DecisionEvent.id.asc())
        .all()
    )


def _decision_buy_rows(db: Session, *, trade_date: date, ticker: str | None = None) -> list[DecisionEvent]:
    start_dt, end_dt = _decision_trade_day_bounds(trade_date)
    query = db.query(DecisionEvent).filter(
        DecisionEvent.decision_type == "buy",
        DecisionEvent.decision_ts >= start_dt,
        DecisionEvent.decision_ts < end_dt,
    )
    if ticker:
        query = query.filter(DecisionEvent.ticker == ticker.upper())
    return (
        query.order_by(DecisionEvent.ticker.asc(), DecisionEvent.decision_ts.asc(), DecisionEvent.id.asc()).all()
    )


def _normalize_route_ts(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _payload_float(payload_text: str | None, *keys: str) -> float | None:
    try:
        payload = json.loads(payload_text or "{}")
    except json.JSONDecodeError:
        return None
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _paired_decision_outcomes(rows: list[DecisionEvent]) -> list[dict]:
    buys_by_ticker: dict[str, list[DecisionEvent]] = {}
    sells_by_ticker: dict[str, list[DecisionEvent]] = {}
    for row in rows:
        if row.decision_type == "buy":
            buys_by_ticker.setdefault(row.ticker, []).append(row)
        elif row.decision_type == "sell":
            sells_by_ticker.setdefault(row.ticker, []).append(row)

    paired: list[dict] = []
    for ticker in sorted(set(buys_by_ticker) | set(sells_by_ticker)):
        buys = buys_by_ticker.get(ticker, [])
        sells = sells_by_ticker.get(ticker, [])
        for idx, (buy_row, sell_row) in enumerate(zip(buys, sells), start=1):
            buy_price = _payload_float(buy_row.decision_payload, "current_close")
            sell_price = _payload_float(sell_row.decision_payload, "current_close", "entry_price")
            if buy_price is None or sell_price is None or buy_price == 0:
                continue
            pnl_abs = round(sell_price - buy_price, 4)
            pnl_pct = round(((sell_price / buy_price) - 1.0) * 100.0, 3)
            paired.append(
                {
                    "reason_code": sell_row.reason_code,
                    "ticker": ticker,
                    "trade_n": idx,
                    "buy_ts": buy_row.decision_ts,
                    "sell_ts": sell_row.decision_ts,
                    "buy_price": buy_price,
                    "sell_price": sell_price,
                    "pnl_abs": pnl_abs,
                    "pnl_pct": pnl_pct,
                }
            )
    return paired


def _nearest_second_bar(
    db: Session,
    *,
    ticker: str,
    event_ts: datetime,
    window_seconds: int = 5,
) -> PolygonSecondAggregate | None:
    normalized_ts = _normalize_route_ts(event_ts)
    window_start = normalized_ts - timedelta(seconds=window_seconds)
    window_end = normalized_ts + timedelta(seconds=window_seconds)
    candidates = (
        db.query(PolygonSecondAggregate)
        .filter(
            PolygonSecondAggregate.ticker == ticker,
            PolygonSecondAggregate.second_ts >= window_start,
            PolygonSecondAggregate.second_ts <= window_end,
        )
        .all()
    )
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda row: (abs((row.second_ts - normalized_ts).total_seconds()), row.second_ts),
    )


def _nearest_minute_bar(
    db: Session,
    *,
    ticker: str,
    event_ts: datetime,
    window_minutes: int = 5,
) -> PolygonMinuteAggregate | None:
    normalized_ts = _normalize_route_ts(event_ts)
    window_start = normalized_ts - timedelta(minutes=window_minutes)
    window_end = normalized_ts + timedelta(minutes=window_minutes)
    candidates = (
        db.query(PolygonMinuteAggregate)
        .filter(
            PolygonMinuteAggregate.ticker == ticker,
            PolygonMinuteAggregate.minute_ts >= window_start,
            PolygonMinuteAggregate.minute_ts <= window_end,
        )
        .all()
    )
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda row: (abs((row.minute_ts - normalized_ts).total_seconds()), row.minute_ts),
    )


def _decision_sell_query(
    db: Session,
    *,
    trade_date: date,
    reason_code: str | None = None,
    ticker: str | None = None,
):
    start_dt, end_dt = _decision_trade_day_bounds(trade_date)
    query = db.query(DecisionEvent).filter(
        DecisionEvent.decision_type == "sell",
        DecisionEvent.decision_ts >= start_dt,
        DecisionEvent.decision_ts < end_dt,
    )
    if reason_code:
        query = query.filter(DecisionEvent.reason_code == reason_code)
    if ticker:
        query = query.filter(DecisionEvent.ticker == ticker.upper())
    return query


def _prefetch_second_bar_index(
    db: Session,
    *,
    tickers: set[str],
    event_timestamps: list[datetime],
    window_seconds: int = 5,
) -> dict[str, tuple[list[datetime], list[PolygonSecondAggregate]]]:
    if not tickers or not event_timestamps:
        return {}
    normalized = [_normalize_route_ts(value) for value in event_timestamps]
    start_dt = min(normalized) - timedelta(seconds=window_seconds)
    end_dt = max(normalized) + timedelta(seconds=window_seconds)
    rows = (
        db.query(PolygonSecondAggregate)
        .filter(
            PolygonSecondAggregate.ticker.in_(sorted(tickers)),
            PolygonSecondAggregate.second_ts >= start_dt,
            PolygonSecondAggregate.second_ts <= end_dt,
        )
        .order_by(PolygonSecondAggregate.ticker.asc(), PolygonSecondAggregate.second_ts.asc())
        .all()
    )
    grouped: dict[str, list[PolygonSecondAggregate]] = {}
    for row in rows:
        grouped.setdefault(row.ticker, []).append(row)
    return {
        ticker: ([row.second_ts for row in group], group)
        for ticker, group in grouped.items()
    }


def _prefetch_minute_bar_index(
    db: Session,
    *,
    tickers: set[str],
    event_timestamps: list[datetime],
    window_minutes: int = 5,
) -> dict[str, tuple[list[datetime], list[PolygonMinuteAggregate]]]:
    if not tickers or not event_timestamps:
        return {}
    normalized = [_normalize_route_ts(value) for value in event_timestamps]
    start_dt = min(normalized) - timedelta(minutes=window_minutes)
    end_dt = max(normalized) + timedelta(minutes=window_minutes)
    rows = (
        db.query(PolygonMinuteAggregate)
        .filter(
            PolygonMinuteAggregate.ticker.in_(sorted(tickers)),
            PolygonMinuteAggregate.minute_ts >= start_dt,
            PolygonMinuteAggregate.minute_ts <= end_dt,
        )
        .order_by(PolygonMinuteAggregate.ticker.asc(), PolygonMinuteAggregate.minute_ts.asc())
        .all()
    )
    grouped: dict[str, list[PolygonMinuteAggregate]] = {}
    for row in rows:
        grouped.setdefault(row.ticker, []).append(row)
    return {
        ticker: ([row.minute_ts for row in group], group)
        for ticker, group in grouped.items()
    }


def _nearest_from_index(index, *, ticker: str, event_ts: datetime):
    bucket = index.get(ticker)
    if bucket is None:
        return None
    timestamps, rows = bucket
    if not rows:
        return None
    target = _normalize_route_ts(event_ts)
    pos = bisect_left(timestamps, target)
    candidates = []
    if pos > 0:
        candidates.append(rows[pos - 1])
    if pos < len(rows):
        candidates.append(rows[pos])
    if pos + 1 < len(rows):
        candidates.append(rows[pos + 1])
    if not candidates:
        return None

    def _bar_ts(row):
        if hasattr(row, "second_ts"):
            return row.second_ts
        return row.minute_ts

    return min(
        candidates,
        key=lambda row: (
            abs((_normalize_route_ts(_bar_ts(row)) - target).total_seconds()),
            _bar_ts(row),
        ),
    )


def _build_market_validation_rows(
    db: Session,
    *,
    sells: list[DecisionEvent],
    buys_by_ticker: dict[str, list[DecisionEvent]],
) -> list[dict]:
    if not sells:
        return []

    relevant_buys: list[DecisionEvent] = []
    for sell in sells:
        prior_buys = buys_by_ticker.get(sell.ticker, [])
        normalized_sell_ts = _normalize_route_ts(sell.decision_ts)
        for candidate in reversed(prior_buys):
            if _normalize_route_ts(candidate.decision_ts) <= normalized_sell_ts:
                relevant_buys.append(candidate)
                break

    tickers = {row.ticker for row in sells} | {row.ticker for row in relevant_buys}
    event_timestamps = [row.decision_ts for row in sells] + [row.decision_ts for row in relevant_buys]
    second_index = _prefetch_second_bar_index(db, tickers=tickers, event_timestamps=event_timestamps)
    minute_index = _prefetch_minute_bar_index(db, tickers=tickers, event_timestamps=event_timestamps)

    items: list[dict] = []
    for sell in sorted(sells, key=lambda row: (row.decision_ts, row.ticker, row.id)):
        prior_buys = buys_by_ticker.get(sell.ticker, [])
        buy = None
        normalized_sell_ts = _normalize_route_ts(sell.decision_ts)
        for candidate in reversed(prior_buys):
            if _normalize_route_ts(candidate.decision_ts) <= normalized_sell_ts:
                buy = candidate
                break

        buy_price_from_event = _payload_float(buy.decision_payload if buy is not None else None, "current_close", "entry_price")
        sell_price_from_event = _payload_float(sell.decision_payload, "current_close", "entry_price")
        buy_second_bar = _nearest_from_index(second_index, ticker=sell.ticker, event_ts=buy.decision_ts) if buy is not None else None
        sell_second_bar = _nearest_from_index(second_index, ticker=sell.ticker, event_ts=sell.decision_ts)
        buy_minute_bar = _nearest_from_index(minute_index, ticker=sell.ticker, event_ts=buy.decision_ts) if buy is not None else None
        sell_minute_bar = _nearest_from_index(minute_index, ticker=sell.ticker, event_ts=sell.decision_ts)

        if buy is None:
            match_status = "NO_PRIOR_BUY"
        elif buy_second_bar is None:
            match_status = "BUY_BAR_NOT_FOUND"
        elif sell_second_bar is None:
            match_status = "SELL_BAR_NOT_FOUND"
        else:
            match_status = "MATCHED"

        buy_second_market = float(buy_second_bar.close) if buy_second_bar is not None else None
        sell_second_market = float(sell_second_bar.close) if sell_second_bar is not None else None
        second_market_pnl_abs = (
            round(sell_second_market - buy_second_market, 4)
            if buy_second_market is not None and sell_second_market is not None
            else None
        )
        second_market_pnl_pct = (
            round((((sell_second_market / buy_second_market) - 1.0) * 100.0), 3)
            if buy_second_market not in (None, 0.0) and sell_second_market is not None
            else None
        )
        buy_minute_market = float(buy_minute_bar.close) if buy_minute_bar is not None else None
        sell_minute_market = float(sell_minute_bar.close) if sell_minute_bar is not None else None
        minute_market_pnl_abs = (
            round(sell_minute_market - buy_minute_market, 4)
            if buy_minute_market is not None and sell_minute_market is not None
            else None
        )
        minute_market_pnl_pct = (
            round((((sell_minute_market / buy_minute_market) - 1.0) * 100.0), 3)
            if buy_minute_market not in (None, 0.0) and sell_minute_market is not None
            else None
        )

        items.append(
            {
                "ticker": sell.ticker,
                "reason_code": sell.reason_code,
                "buy_id": buy.id if buy is not None else None,
                "buy_ts": buy.decision_ts if buy is not None else None,
                "sell_id": sell.id,
                "sell_ts": sell.decision_ts,
                "match_status": match_status,
                "buy_price_from_event": buy_price_from_event,
                "sell_price_from_event": sell_price_from_event,
                "buy_second_bar_ts": buy_second_bar.second_ts if buy_second_bar is not None else None,
                "buy_price_from_second_market": buy_second_market,
                "sell_second_bar_ts": sell_second_bar.second_ts if sell_second_bar is not None else None,
                "sell_price_from_second_market": sell_second_market,
                "second_market_pnl_abs": second_market_pnl_abs,
                "second_market_pnl_pct": second_market_pnl_pct,
                "buy_minute_bar_ts": buy_minute_bar.minute_ts if buy_minute_bar is not None else None,
                "buy_price_from_minute_market": buy_minute_market,
                "sell_minute_bar_ts": sell_minute_bar.minute_ts if sell_minute_bar is not None else None,
                "sell_price_from_minute_market": sell_minute_market,
                "minute_market_pnl_abs": minute_market_pnl_abs,
                "minute_market_pnl_pct": minute_market_pnl_pct,
            }
        )
    return items


def _decision_market_validation_rows(
    db: Session,
    *,
    trade_date: date,
    reason_code: str | None = None,
    ticker: str | None = None,
) -> list[dict]:
    sells = (
        _decision_sell_query(
            db,
            trade_date=trade_date,
            reason_code=reason_code,
            ticker=ticker,
        )
        .order_by(DecisionEvent.decision_ts.asc(), DecisionEvent.ticker.asc(), DecisionEvent.id.asc())
        .all()
    )
    buys_by_ticker: dict[str, list[DecisionEvent]] = {}
    for row in _decision_buy_rows(db, trade_date=trade_date, ticker=ticker):
        buys_by_ticker.setdefault(row.ticker, []).append(row)
    return _build_market_validation_rows(db, sells=sells, buys_by_ticker=buys_by_ticker)


def _under_ten_aggregate_filter(model, *, max_price: float):
    return model.high < max_price


def _under_ten_tick_filter(model, *, max_price: float):
    return and_(
        model.bid < max_price,
        model.ask < max_price,
        model.last < max_price,
    )


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


async def _read_runtime_snapshot(request: Request) -> dict:
    cache = getattr(request.app.state, "cache", None)
    if cache is None:
        return {}
    try:
        snapshot = await cache.get_runtime_snapshot()
    except Exception:
        log.exception("analytics.runtime_snapshot_read_failed")
        return {}
    return snapshot or {}


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
@track_tables("universe_daily", "symbols")
def get_universe(active_only: bool = False, db: Session = Depends(get_db)):
    """Get the latest flatfile-driven market universe with operational status overlay."""
    latest_trade_date = (
        db.query(UniverseDaily.trade_date)
        .filter(UniverseDaily.universe_kind == UNIVERSE_KIND_MARKET)
        .filter(UniverseDaily.source.in_(_market_universe_sources()))
        .order_by(UniverseDaily.trade_date.desc())
        .limit(1)
        .scalar()
    )
    if latest_trade_date is None:
        return []

    rows = (
        db.query(UniverseDaily, Symbol)
        .outerjoin(Symbol, Symbol.ticker == UniverseDaily.ticker)
        .filter(UniverseDaily.trade_date == latest_trade_date)
        .filter(UniverseDaily.universe_kind == UNIVERSE_KIND_MARKET)
        .filter(UniverseDaily.source.in_(_market_universe_sources()))
        .order_by(UniverseDaily.ticker.asc())
        .all()
    )

    response_rows: list[SymbolRead] = []
    for universe_row, symbol_row in rows:
        is_active = bool(symbol_row.is_active) if symbol_row is not None else False
        if active_only and not is_active:
            continue
        row_created_at = universe_row.created_at
        row_updated_at = symbol_row.updated_at if symbol_row is not None else universe_row.created_at
        response_rows.append(
            SymbolRead(
                id=universe_row.id,
                ticker=universe_row.ticker,
                name=(symbol_row.name if symbol_row is not None else "") or "",
                exchange=universe_row.exchange or (symbol_row.exchange if symbol_row is not None else "NASDAQ"),
                last_price=universe_row.last_price if universe_row.last_price is not None else (
                    symbol_row.last_price if symbol_row is not None else None
                ),
                avg_volume=universe_row.avg_volume if universe_row.avg_volume is not None else (
                    symbol_row.avg_volume if symbol_row is not None else None
                ),
                is_active=is_active,
                created_at=row_created_at,
                updated_at=row_updated_at,
            )
        )
    return response_rows


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
    polygon_snapshot = (await _read_runtime_snapshot(request)).get("polygon_session") or None
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
    query = (
        db.query(UniverseDaily)
        .filter(UniverseDaily.universe_kind == UNIVERSE_KIND_MARKET)
        .filter(UniverseDaily.source.in_(_market_universe_sources()))
    )
    if trade_date is None:
        latest_trade_date = (
            db.query(UniverseDaily.trade_date)
            .filter(UniverseDaily.universe_kind == UNIVERSE_KIND_MARKET)
            .filter(UniverseDaily.source.in_(_market_universe_sources()))
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


@router.get("/polygon/flatfiles/day-aggregates/download")
def download_polygon_day_aggregate_flatfile(
    trade_date: str,
    db: Session = Depends(get_db),
):
    try:
        selected_trade_date = date.fromisoformat(trade_date)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid trade_date") from exc

    loader = PolygonFlatFileUniverseLoader(db)
    try:
        response = loader.fetch_day_aggregate_object(selected_trade_date)
    except Exception as exc:
        if loader._is_missing_object_error(exc):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No Polygon flatfile found for trade_date={selected_trade_date.isoformat()}",
            ) from exc
        upstream_code = None
        upstream_response = getattr(exc, "response", None)
        if isinstance(upstream_response, dict):
            upstream_code = str(upstream_response.get("Error", {}).get("Code", "")).strip() or None
        log.exception(
            "secret_sauce.flatfile_download_failed",
            trade_date=selected_trade_date.isoformat(),
            upstream_code=upstream_code,
            bucket=settings.polygon_flatfiles_bucket,
            endpoint_url=settings.polygon_flatfiles_endpoint_url,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Polygon flatfile fetch failed",
        ) from exc

    body = response["Body"]
    filename = PolygonFlatFileUniverseLoader.build_day_aggregate_filename(selected_trade_date)
    content_length = response.get("ContentLength")
    media_type = response.get("ContentType") or "application/gzip"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control": "no-store",
    }
    if content_length is not None:
        headers["Content-Length"] = str(content_length)

    def stream_bytes():
        try:
            while True:
                chunk = body.read(1024 * 1024)
                if not chunk:
                    break
                yield chunk
        finally:
            with suppress(Exception):
                body.close()

    return StreamingResponse(stream_bytes(), media_type=media_type, headers=headers)


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
            .filter(UniverseDaily.universe_kind == UNIVERSE_KIND_MARKET)
            .filter(UniverseDaily.source.in_(_market_universe_sources()))
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
        .filter(UniverseDaily.universe_kind == UNIVERSE_KIND_MARKET)
        .filter(UniverseDaily.source.in_(_market_universe_sources()))
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
        universe_tickers = _latest_universe_tickers(
            db,
            max_price=settings.secret_universe_max_price,
            allow_symbol_fallback=False,
        )
        if not universe_tickers:
            return PolygonDayAggregatePageResponse(
                items=[],
                total=0,
                page=page,
                page_size=page_size,
                trade_date=selected_trade_date,
            )
        query = query.filter(PolygonDayAggregate.ticker.in_(universe_tickers))
        query = query.filter(_under_ten_aggregate_filter(PolygonDayAggregate, max_price=settings.secret_universe_max_price))
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
    session_end_et: dt_time | None = None,
    session_time_et: dt_time | None = None,
    universe_only: bool = True,
    db: Session = Depends(get_db),
):
    latest_live_ts = _source_latest_timestamp(
        db,
        model=PolygonMinuteAggregateLive,
        ts_column=PolygonMinuteAggregateLive.minute_ts,
    )
    latest_history_ts = _source_latest_timestamp(
        db,
        model=PolygonMinuteAggregate,
        ts_column=PolygonMinuteAggregate.minute_ts,
    )
    if trade_date is not None:
        selected_trade_date = trade_date
    else:
        candidate_trade_dates = [
            _intraday_trade_day(ts)
            for ts in (latest_live_ts, latest_history_ts)
            if ts is not None
        ]
        selected_trade_date = max(candidate_trade_dates) if candidate_trade_dates else None

    latest_available_ts = latest_live_ts
    query = db.query(PolygonMinuteAggregateLive)
    if universe_only:
        universe_tickers = _latest_universe_tickers(
            db,
            max_price=settings.secret_universe_max_price,
            allow_symbol_fallback=False,
        )
        if not universe_tickers:
            return PolygonMinuteAggregatePageResponse(
                items=[],
                total=0,
                page=page,
                page_size=page_size,
                trade_date=selected_trade_date,
            )
        query = query.filter(PolygonMinuteAggregateLive.ticker.in_(universe_tickers))
        query = query.filter(_under_ten_aggregate_filter(PolygonMinuteAggregateLive, max_price=settings.secret_universe_max_price))
    if selected_trade_date:
        start_dt, end_dt = _intraday_trade_day_bounds(selected_trade_date)
        query = query.filter(
            PolygonMinuteAggregateLive.minute_ts >= start_dt,
            PolygonMinuteAggregateLive.minute_ts < end_dt,
        )
    requested_session_start = session_start_et or session_time_et or REGULAR_MARKET_OPEN
    requested_session_end = session_end_et or REGULAR_MARKET_CLOSE
    if selected_trade_date is not None:
        session_start_utc, session_end_utc = _session_bounds_for_trade_date(
            selected_trade_date,
            session_start_et=requested_session_start,
            session_end_et=requested_session_end,
        )
        query = query.filter(
            PolygonMinuteAggregateLive.minute_ts >= session_start_utc,
            PolygonMinuteAggregateLive.minute_ts < session_end_utc,
        )
    if ticker:
        query = query.filter(PolygonMinuteAggregateLive.ticker == ticker.upper())
    rows = (
        query.order_by(PolygonMinuteAggregateLive.minute_ts.desc(), PolygonMinuteAggregateLive.id.desc())
        .offset(page * page_size)
        .limit(page_size)
        .all()
    )
    if rows:
        return PolygonMinuteAggregatePageResponse(
            items=[PolygonMinuteAggregateResponse.model_validate(row) for row in rows],
            total=None,
            page=page,
            page_size=page_size,
            trade_date=selected_trade_date,
            source="live",
            latest_available_ts=latest_live_ts,
            is_stale=selected_trade_date is not None
            and (latest_live_ts is None or _intraday_trade_day(latest_live_ts) != selected_trade_date),
        )

    history_query = db.query(PolygonMinuteAggregate)
    if universe_only:
        universe_tickers = _latest_universe_tickers(
            db,
            max_price=settings.secret_universe_max_price,
            allow_symbol_fallback=False,
        )
        if not universe_tickers:
            return PolygonMinuteAggregatePageResponse(
                items=[],
                total=0,
                page=page,
                page_size=page_size,
                trade_date=selected_trade_date,
                source="history",
                latest_available_ts=latest_history_ts,
                is_stale=selected_trade_date is not None
                and (latest_history_ts is None or _intraday_trade_day(latest_history_ts) != selected_trade_date),
            )
        history_query = history_query.filter(PolygonMinuteAggregate.ticker.in_(universe_tickers))
        history_query = history_query.filter(
            _under_ten_aggregate_filter(PolygonMinuteAggregate, max_price=settings.secret_universe_max_price)
        )
    if selected_trade_date:
        start_dt, end_dt = _intraday_trade_day_bounds(selected_trade_date)
        history_query = history_query.filter(
            PolygonMinuteAggregate.minute_ts >= start_dt,
            PolygonMinuteAggregate.minute_ts < end_dt,
        )
    if selected_trade_date is not None:
        session_start_utc, session_end_utc = _session_bounds_for_trade_date(
            selected_trade_date,
            session_start_et=requested_session_start,
            session_end_et=requested_session_end,
        )
        history_query = history_query.filter(
            PolygonMinuteAggregate.minute_ts >= session_start_utc,
            PolygonMinuteAggregate.minute_ts < session_end_utc,
        )
    if ticker:
        history_query = history_query.filter(PolygonMinuteAggregate.ticker == ticker.upper())
    history_total = history_query.count()
    history_rows = (
        history_query.order_by(PolygonMinuteAggregate.minute_ts.desc(), PolygonMinuteAggregate.id.desc())
        .offset(page * page_size)
        .limit(page_size)
        .all()
    )
    return PolygonMinuteAggregatePageResponse(
        items=[PolygonMinuteAggregateResponse.model_validate(row) for row in history_rows],
        total=history_total,
        page=page,
        page_size=page_size,
        trade_date=selected_trade_date,
        source="history",
        latest_available_ts=latest_history_ts,
        is_stale=selected_trade_date is not None
        and (latest_history_ts is None or _intraday_trade_day(latest_history_ts) != selected_trade_date),
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
    selected_trade_date = _resolve_canonical_intraday_trade_date(
        db,
        explicit_trade_date=trade_date,
        model=PolygonMinuteAggregate,
        ts_column=PolygonMinuteAggregate.minute_ts,
    )
    latest_available_ts = _source_latest_timestamp(
        db,
        model=PolygonMinuteAggregate,
        ts_column=PolygonMinuteAggregate.minute_ts,
    )
    if universe_only:
        universe_tickers = _latest_universe_tickers(
            db,
            max_price=settings.secret_universe_max_price,
            allow_symbol_fallback=False,
        )
        if not universe_tickers:
            return PolygonMinuteAggregatePageResponse(
                items=[],
                total=0,
                page=page,
                page_size=page_size,
                trade_date=selected_trade_date,
            )
        query = query.filter(PolygonMinuteAggregate.ticker.in_(universe_tickers))
        query = query.filter(_under_ten_aggregate_filter(PolygonMinuteAggregate, max_price=settings.secret_universe_max_price))
    if selected_trade_date is not None:
        start_dt, end_dt = _intraday_trade_day_bounds(selected_trade_date)
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
        source="history",
        latest_available_ts=latest_available_ts,
        is_stale=selected_trade_date is not None
        and (latest_available_ts is None or _intraday_trade_day(latest_available_ts) != selected_trade_date),
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
    session_end_et: dt_time | None = None,
    session_time_et: dt_time | None = None,
    universe_only: bool = True,
    db: Session = Depends(get_db),
):
    query = db.query(PolygonSecondAggregateLive)
    selected_trade_date = _resolve_canonical_intraday_trade_date(
        db,
        explicit_trade_date=trade_date,
        model=PolygonSecondAggregateLive,
        ts_column=PolygonSecondAggregateLive.second_ts,
    )
    latest_available_ts = _source_latest_timestamp(
        db,
        model=PolygonSecondAggregateLive,
        ts_column=PolygonSecondAggregateLive.second_ts,
    )
    if universe_only:
        universe_tickers = _latest_universe_tickers(
            db,
            max_price=settings.secret_universe_max_price,
            allow_symbol_fallback=False,
        )
        if not universe_tickers:
            return PolygonSecondAggregatePageResponse(
                items=[],
                total=0,
                page=page,
                page_size=page_size,
                trade_date=selected_trade_date,
            )
        query = query.filter(PolygonSecondAggregateLive.ticker.in_(universe_tickers))
        query = query.filter(_under_ten_aggregate_filter(PolygonSecondAggregateLive, max_price=settings.secret_universe_max_price))
    if selected_trade_date is not None:
        start_dt, end_dt = _intraday_trade_day_bounds(selected_trade_date)
        query = query.filter(PolygonSecondAggregateLive.second_ts >= start_dt, PolygonSecondAggregateLive.second_ts < end_dt)
    requested_session_start = session_start_et or session_time_et or REGULAR_MARKET_OPEN
    requested_session_end = session_end_et or REGULAR_MARKET_CLOSE
    if selected_trade_date is not None:
        session_start_utc, session_end_utc = _session_bounds_for_trade_date(
            selected_trade_date,
            session_start_et=requested_session_start,
            session_end_et=requested_session_end,
        )
        query = query.filter(
            PolygonSecondAggregateLive.second_ts >= session_start_utc,
            PolygonSecondAggregateLive.second_ts < session_end_utc,
        )
    if ticker:
        query = query.filter(PolygonSecondAggregateLive.ticker == ticker.upper())
    rows = (
        query.order_by(PolygonSecondAggregateLive.second_ts.desc(), PolygonSecondAggregateLive.ticker.asc())
        .offset(page * page_size)
        .limit(page_size)
        .all()
    )
    return PolygonSecondAggregatePageResponse(
        items=[PolygonSecondAggregateResponse.model_validate(row) for row in rows],
        total=None,
        page=page,
        page_size=page_size,
        trade_date=selected_trade_date,
        source="live",
        latest_available_ts=latest_available_ts,
        is_stale=selected_trade_date is not None
        and (latest_available_ts is None or _intraday_trade_day(latest_available_ts) != selected_trade_date),
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
    selected_trade_date = _resolve_canonical_intraday_trade_date(
        db,
        explicit_trade_date=trade_date,
        model=PolygonSecondAggregate,
        ts_column=PolygonSecondAggregate.second_ts,
    )
    latest_available_ts = _source_latest_timestamp(
        db,
        model=PolygonSecondAggregate,
        ts_column=PolygonSecondAggregate.second_ts,
    )
    if universe_only:
        universe_tickers = _latest_universe_tickers(
            db,
            max_price=settings.secret_universe_max_price,
            allow_symbol_fallback=False,
        )
        if not universe_tickers:
            return PolygonSecondAggregatePageResponse(
                items=[],
                total=0,
                page=page,
                page_size=page_size,
                trade_date=selected_trade_date,
            )
        query = query.filter(PolygonSecondAggregate.ticker.in_(universe_tickers))
        query = query.filter(_under_ten_aggregate_filter(PolygonSecondAggregate, max_price=settings.secret_universe_max_price))
    if selected_trade_date is not None:
        start_dt, end_dt = _intraday_trade_day_bounds(selected_trade_date)
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
        source="history",
        latest_available_ts=latest_available_ts,
        is_stale=selected_trade_date is not None
        and (latest_available_ts is None or _intraday_trade_day(latest_available_ts) != selected_trade_date),
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
        universe_tickers = _latest_universe_tickers(
            db,
            max_price=settings.secret_universe_max_price,
            allow_symbol_fallback=False,
        )
        if not universe_tickers:
            return PolygonTickPageResponse(
                items=[],
                page_size=page_size,
                trade_date=selected_trade_date,
                next_cursor=None,
                has_more=False,
            )
        query = query.filter(PolygonTickLive.ticker.in_(universe_tickers))
        query = query.filter(_under_ten_tick_filter(PolygonTickLive, max_price=settings.secret_universe_max_price))
    if selected_trade_date:
        start_dt = datetime.combine(selected_trade_date, datetime.min.time())
        end_dt = start_dt + timedelta(days=1)
        query = query.filter(PolygonTickLive.tick_ts >= start_dt, PolygonTickLive.tick_ts < end_dt)
    if normalized_ticker:
        query = query.filter(PolygonTickLive.ticker == normalized_ticker)
    if event_type:
        query = query.filter(PolygonTickLive.event_type == event_type.lower())
    query = _deduped_tick_query(db, query, PolygonTickLive)
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
        total=len(visible_rows),
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
        universe_tickers = _latest_universe_tickers(
            db,
            max_price=settings.secret_universe_max_price,
            allow_symbol_fallback=False,
        )
        if not universe_tickers:
            return PolygonTickPageResponse(
                items=[],
                total=0,
                page=page,
                page_size=page_size,
                trade_date=selected_trade_date,
            )
        query = query.filter(PolygonTick.ticker.in_(universe_tickers))
        query = query.filter(_under_ten_tick_filter(PolygonTick, max_price=settings.secret_universe_max_price))
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
        universe_tickers = _latest_universe_tickers(
            db,
            max_price=settings.secret_universe_max_price,
        )
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
        "watching": status_counts.get("idle", 0),
        "candidate": status_counts.get("candidate", 0) + status_counts.get("validated", 0),
        "buy": status_counts.get("buy", 0),
        "manage": status_counts.get("manage", 0),
        "sold": status_counts.get("sold", 0),
        "rejected": status_counts.get("rejected", 0),
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
        universe_tickers = _universe_tickers_for_trade_date(
            db,
            trade_date=selected_trade_date,
            max_price=settings.secret_universe_max_price,
        )
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
        latest_intraday_ts_candidates = [
            _source_latest_timestamp(db, model=PolygonMinuteAggregateLive, ts_column=PolygonMinuteAggregateLive.minute_ts),
            _source_latest_timestamp(db, model=PolygonSecondAggregateLive, ts_column=PolygonSecondAggregateLive.second_ts),
        ]
        latest_intraday_ts = max((value for value in latest_intraday_ts_candidates if value is not None), default=None)
        if latest_intraday_ts is not None:
            selected_trade_date = latest_intraday_ts.date()
        else:
            latest_decision_ts = db.query(func.max(DecisionEvent.decision_ts)).scalar()
            if latest_decision_ts is not None:
                selected_trade_date = latest_decision_ts.date()
            else:
                selected_trade_date = _default_decision_trade_day()
    if universe_only:
        universe_tickers = _universe_tickers_for_trade_date(
            db,
            trade_date=selected_trade_date,
            max_price=settings.secret_universe_max_price,
        )
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
async def ml_status(request: Request, db: Session = Depends(get_db)):
    """Get ML model status and configuration."""
    classifier = getattr(request.app.state, "classifier", None)
    active_model = ModelRegistryService(db).active_model()
    return MLStatusResponse(
        model_trained=classifier.is_trained if classifier else False,
        feature_importances=classifier.feature_importances() if classifier and classifier.is_trained else None,
        ml_enabled=settings.ml_enabled,
        ml_confidence_weight=settings.ml_confidence_weight,
        min_training_samples=settings.ml_min_training_samples,
        active_model_version=active_model.model_version if active_model else None,
        active_model_trained_at=active_model.trained_at if active_model else None,
        active_model_sample_count=active_model.training_sample_count if active_model else None,
        active_model_status=active_model.status if active_model else None,
        active_model_artifact_uri=active_model.artifact_uri if active_model else None,
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


@router.get("/analytics/runtime-kpis", response_model=DecisionRuntimeKpiResponse)
@track_tables("candidate_events", "decision_events", "symbol_state_live", "minute_aggregates_live", "second_aggregates_live")
async def analytics_runtime_kpis(
    request: Request,
    trade_date: date | None = None,
    window_minutes: int = 10,
    db: Session = Depends(get_db),
):
    window_minutes = max(1, min(window_minutes, 240))
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    window_start = now_utc - timedelta(minutes=window_minutes)
    latest_intraday_ts_candidates = [
        _source_latest_timestamp(db, model=PolygonMinuteAggregateLive, ts_column=PolygonMinuteAggregateLive.minute_ts),
        _source_latest_timestamp(db, model=PolygonSecondAggregateLive, ts_column=PolygonSecondAggregateLive.second_ts),
    ]
    latest_intraday_ts = max((value for value in latest_intraday_ts_candidates if value is not None), default=None)
    selected_trade_date = trade_date or (latest_intraday_ts.date() if latest_intraday_ts is not None else _default_decision_trade_day())
    session_start_utc, session_end_utc = _session_bounds_for_trade_date(
        selected_trade_date,
        session_start_et=REGULAR_MARKET_OPEN,
        session_end_et=REGULAR_MARKET_CLOSE,
    )

    candidate_events_window_count = (
        db.query(func.count(CandidateEvent.id))
        .filter(CandidateEvent.created_at >= window_start)
        .scalar()
        or 0
    )
    processed_candidate_events_window_count = (
        db.query(func.count(CandidateEvent.id))
        .filter(
            CandidateEvent.created_at >= window_start,
            CandidateEvent.processed_at.is_not(None),
        )
        .scalar()
        or 0
    )
    unprocessed_candidate_events_window_count = (
        db.query(func.count(CandidateEvent.id))
        .filter(
            CandidateEvent.created_at >= window_start,
            CandidateEvent.processed_at.is_(None),
        )
        .scalar()
        or 0
    )

    decision_counts = {
        row[0]: row[1]
        for row in (
            db.query(DecisionEvent.decision_type, func.count(DecisionEvent.id))
            .filter(DecisionEvent.created_at >= window_start)
            .group_by(DecisionEvent.decision_type)
            .all()
        )
    }
    stale_reject_counts = {
        row[0]: row[1]
        for row in (
            db.query(DecisionEvent.reason_code, func.count(DecisionEvent.id))
            .filter(
                DecisionEvent.created_at >= window_start,
                DecisionEvent.decision_type == "reject",
                DecisionEvent.reason_code.in_(("second_stream_stale", "minute_stream_stale")),
            )
            .group_by(DecisionEvent.reason_code)
            .all()
        )
    }
    second_stale_symbols_count = (
        db.query(func.count(SymbolStateLive.ticker))
        .filter(SymbolStateLive.is_second_stream_stale.is_(True))
        .scalar()
        or 0
    )
    minute_stale_symbols_count = (
        db.query(func.count(SymbolStateLive.ticker))
        .filter(SymbolStateLive.is_minute_stream_stale.is_(True))
        .scalar()
        or 0
    )
    universe_tickers = _latest_universe_tickers(
        db,
        max_price=settings.secret_universe_max_price,
        allow_symbol_fallback=False,
    )
    runtime_snapshot = await _read_runtime_snapshot(request)
    polygon_snapshot: dict[str, object] = runtime_snapshot.get("polygon_session") or {}
    aggregate_stream_snapshot: dict[str, object] = runtime_snapshot.get("aggregate_stream") or {}
    trigger_stream_snapshot: dict[str, object] = runtime_snapshot.get("trigger_stream") or {}
    persistence_snapshot: dict[str, object] = runtime_snapshot.get("persistence") or {}

    minute_live_row_count = 0
    second_live_row_count = 0
    minute_live_symbol_count = 0
    second_live_symbol_count = 0
    minute_without_second_symbol_count = 0
    if universe_tickers:
        minute_live_query = db.query(PolygonMinuteAggregateLive).filter(
            PolygonMinuteAggregateLive.ticker.in_(universe_tickers),
            _under_ten_aggregate_filter(PolygonMinuteAggregateLive, max_price=settings.secret_universe_max_price),
            PolygonMinuteAggregateLive.minute_ts >= session_start_utc,
            PolygonMinuteAggregateLive.minute_ts < session_end_utc,
        )
        second_live_query = db.query(PolygonSecondAggregateLive).filter(
            PolygonSecondAggregateLive.ticker.in_(universe_tickers),
            _under_ten_aggregate_filter(PolygonSecondAggregateLive, max_price=settings.secret_universe_max_price),
            PolygonSecondAggregateLive.second_ts >= session_start_utc,
            PolygonSecondAggregateLive.second_ts < session_end_utc,
        )
        minute_live_row_count = minute_live_query.count()
        second_live_row_count = second_live_query.count()
        minute_live_symbol_count = (
            db.query(func.count(func.distinct(PolygonMinuteAggregateLive.ticker)))
            .filter(
                PolygonMinuteAggregateLive.ticker.in_(universe_tickers),
                _under_ten_aggregate_filter(PolygonMinuteAggregateLive, max_price=settings.secret_universe_max_price),
                PolygonMinuteAggregateLive.minute_ts >= session_start_utc,
                PolygonMinuteAggregateLive.minute_ts < session_end_utc,
            )
            .scalar()
            or 0
        )
        second_live_symbol_count = (
            db.query(func.count(func.distinct(PolygonSecondAggregateLive.ticker)))
            .filter(
                PolygonSecondAggregateLive.ticker.in_(universe_tickers),
                _under_ten_aggregate_filter(PolygonSecondAggregateLive, max_price=settings.secret_universe_max_price),
                PolygonSecondAggregateLive.second_ts >= session_start_utc,
                PolygonSecondAggregateLive.second_ts < session_end_utc,
            )
            .scalar()
            or 0
        )
        minute_ticker_subquery = (
            db.query(PolygonMinuteAggregateLive.ticker.label("ticker"))
            .filter(
                PolygonMinuteAggregateLive.ticker.in_(universe_tickers),
                _under_ten_aggregate_filter(PolygonMinuteAggregateLive, max_price=settings.secret_universe_max_price),
                PolygonMinuteAggregateLive.minute_ts >= session_start_utc,
                PolygonMinuteAggregateLive.minute_ts < session_end_utc,
            )
            .distinct()
            .subquery()
        )
        second_ticker_subquery = (
            db.query(PolygonSecondAggregateLive.ticker.label("ticker"))
            .filter(
                PolygonSecondAggregateLive.ticker.in_(universe_tickers),
                _under_ten_aggregate_filter(PolygonSecondAggregateLive, max_price=settings.secret_universe_max_price),
                PolygonSecondAggregateLive.second_ts >= session_start_utc,
                PolygonSecondAggregateLive.second_ts < session_end_utc,
            )
            .distinct()
            .subquery()
        )
        minute_without_second_symbol_count = (
            db.query(func.count())
            .select_from(minute_ticker_subquery)
            .outerjoin(second_ticker_subquery, minute_ticker_subquery.c.ticker == second_ticker_subquery.c.ticker)
            .filter(second_ticker_subquery.c.ticker.is_(None))
            .scalar()
            or 0
        )

    return DecisionRuntimeKpiResponse(
        generated_at=now_utc,
        window_minutes=window_minutes,
        trade_date=selected_trade_date,
        polygon_connected=bool(polygon_snapshot.get("connected", False)),
        polygon_subscriptions_paused=bool(polygon_snapshot.get("subscriptions_paused", False)),
        polygon_subscription_count=int(polygon_snapshot.get("subscription_count", 0) or 0),
        last_minute_aggregate_event_at=polygon_snapshot.get("last_minute_aggregate_event_at"),
        last_second_aggregate_event_at=polygon_snapshot.get("last_second_aggregate_event_at"),
        last_aggregate_persisted_at=polygon_snapshot.get("last_aggregate_persisted_at"),
        last_minute_persisted_at=polygon_snapshot.get("last_minute_persisted_at"),
        last_second_persisted_at=polygon_snapshot.get("last_second_persisted_at"),
        aggregate_stream_pending_count=int(aggregate_stream_snapshot.get("pending_count", 0) or 0),
        aggregate_stream_lag_count=int(aggregate_stream_snapshot.get("lag_count", 0) or 0),
        trigger_stream_pending_count=int(trigger_stream_snapshot.get("pending_count", 0) or 0),
        trigger_stream_lag_count=int(trigger_stream_snapshot.get("lag_count", 0) or 0),
        persistence_last_flush_completed_at=persistence_snapshot.get("last_flush_completed_at"),
        persistence_last_flush_latency_ms=persistence_snapshot.get("last_flush_latency_ms"),
        persistence_last_batch_event_count=int(persistence_snapshot.get("last_batch_event_count", 0) or 0),
        persistence_last_batch_minute_count=int(persistence_snapshot.get("last_batch_minute_count", 0) or 0),
        persistence_last_batch_second_count=int(persistence_snapshot.get("last_batch_second_count", 0) or 0),
        persistence_error_count=int(persistence_snapshot.get("error_count", 0) or 0),
        persistence_last_error_at=persistence_snapshot.get("last_error_at"),
        persistence_last_error_message=persistence_snapshot.get("last_error_message"),
        candidate_events_window_count=candidate_events_window_count,
        processed_candidate_events_window_count=processed_candidate_events_window_count,
        unprocessed_candidate_events_window_count=unprocessed_candidate_events_window_count,
        decision_events_window_count=sum(decision_counts.values()),
        candidate_decision_count=decision_counts.get("candidate", 0),
        buy_decision_count=decision_counts.get("buy", 0),
        manage_decision_count=decision_counts.get("manage", 0),
        sell_decision_count=decision_counts.get("sell", 0),
        reject_decision_count=decision_counts.get("reject", 0),
        second_stream_stale_reject_count=stale_reject_counts.get("second_stream_stale", 0),
        minute_stream_stale_reject_count=stale_reject_counts.get("minute_stream_stale", 0),
        second_stale_symbols_count=second_stale_symbols_count,
        minute_stale_symbols_count=minute_stale_symbols_count,
        minute_live_row_count=minute_live_row_count,
        second_live_row_count=second_live_row_count,
        minute_live_symbol_count=minute_live_symbol_count,
        second_live_symbol_count=second_live_symbol_count,
        minute_without_second_symbol_count=minute_without_second_symbol_count,
    )


@router.get("/analytics/signal-accuracy", response_model=list[SignalAccuracyBucketResponse])
@track_tables("signals", "trades")
def analytics_signal_accuracy(db: Session = Depends(get_db)):
    """Get win rate by signal score bucket."""
    return TradeAnalytics(db).signal_accuracy_by_bucket()


@router.get("/analytics/decision-events/summary", response_model=DecisionOutcomeSummaryResponse)
@track_tables("decision_events")
def analytics_decision_events_summary(
    trade_date: date | None = None,
    db: Session = Depends(get_db),
):
    target_trade_date = trade_date or _default_decision_trade_day()
    paired = _paired_decision_outcomes(_decision_trade_day_rows(db, trade_date=target_trade_date))
    pnl_values = [row["pnl_pct"] for row in paired]
    profitable = sum(1 for row in paired if row["sell_price"] > row["buy_price"])
    losing = sum(1 for row in paired if row["sell_price"] < row["buy_price"])
    flat = sum(1 for row in paired if row["sell_price"] == row["buy_price"])
    avg_pnl = round(sum(pnl_values) / len(pnl_values), 3) if pnl_values else None
    worst_pnl = round(min(pnl_values), 3) if pnl_values else None
    best_pnl = round(max(pnl_values), 3) if pnl_values else None
    return DecisionOutcomeSummaryResponse(
        trade_date=target_trade_date,
        completed_trades=len(paired),
        profitable_sales=profitable,
        losing_sales=losing,
        flat_sales=flat,
        avg_pnl_pct=avg_pnl,
        worst_pnl_pct=worst_pnl,
        best_pnl_pct=best_pnl,
    )


@router.get("/analytics/decision-events/by-reason", response_model=list[DecisionOutcomeByReasonResponse])
@track_tables("decision_events")
def analytics_decision_events_by_reason(
    trade_date: date | None = None,
    db: Session = Depends(get_db),
):
    target_trade_date = trade_date or _default_decision_trade_day()
    paired = _paired_decision_outcomes(_decision_trade_day_rows(db, trade_date=target_trade_date))
    grouped: dict[str, list[dict]] = {}
    for row in paired:
        grouped.setdefault(row["reason_code"], []).append(row)

    items: list[DecisionOutcomeByReasonResponse] = []
    for reason_code, rows in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        pnl_values = [row["pnl_pct"] for row in rows]
        items.append(
            DecisionOutcomeByReasonResponse(
                reason_code=reason_code,
                trades=len(rows),
                profitable_sales=sum(1 for row in rows if row["sell_price"] > row["buy_price"]),
                losing_sales=sum(1 for row in rows if row["sell_price"] < row["buy_price"]),
                flat_sales=sum(1 for row in rows if row["sell_price"] == row["buy_price"]),
                avg_pnl_pct=round(sum(pnl_values) / len(pnl_values), 3) if pnl_values else None,
            )
        )
    return items


@router.get("/analytics/decision-events/details", response_model=list[DecisionOutcomeDetailResponse])
@track_tables("decision_events")
def analytics_decision_events_details(
    trade_date: date | None = None,
    reason_code: str | None = None,
    ticker: str | None = None,
    db: Session = Depends(get_db),
):
    target_trade_date = trade_date or _default_decision_trade_day()
    paired = _paired_decision_outcomes(_decision_trade_day_rows(db, trade_date=target_trade_date))
    items = [
        DecisionOutcomeDetailResponse(**row)
        for row in paired
        if (reason_code is None or row["reason_code"] == reason_code)
        and (ticker is None or row["ticker"] == ticker.upper())
    ]
    items.sort(key=lambda row: (row.reason_code, row.sell_ts, row.ticker))
    return items


@router.get("/analytics/decision-events/duplicate-buys", response_model=list[DuplicateBuyAuditResponse])
@track_tables("decision_events")
def analytics_decision_events_duplicate_buys(
    trade_date: date | None = None,
    db: Session = Depends(get_db),
):
    target_trade_date = trade_date or _default_decision_trade_day()
    rows = _decision_trade_day_rows(db, trade_date=target_trade_date)
    grouped: dict[str, Counter] = {}
    for row in rows:
        counter = grouped.setdefault(row.ticker, Counter())
        counter[row.decision_type] += 1
        counter["total"] += 1
    items = [
        DuplicateBuyAuditResponse(
            ticker=ticker,
            buy_count=counter.get("buy", 0),
            sell_count=counter.get("sell", 0),
            total_count=counter.get("total", 0),
        )
        for ticker, counter in grouped.items()
        if counter.get("buy", 0) > 1
    ]
    items.sort(key=lambda row: (-row.total_count, row.ticker))
    return items


@router.get("/analytics/decision-events/sell-to-buy-churn", response_model=list[SellToBuyChurnAuditResponse])
@track_tables("decision_events")
def analytics_decision_events_sell_to_buy_churn(
    trade_date: date | None = None,
    db: Session = Depends(get_db),
):
    target_trade_date = trade_date or _default_decision_trade_day()
    rows = _decision_trade_day_rows(db, trade_date=target_trade_date)
    rows.sort(key=lambda row: (row.ticker, row.decision_ts, row.id))
    by_ticker: dict[str, list[DecisionEvent]] = {}
    for row in rows:
        by_ticker.setdefault(row.ticker, []).append(row)

    items: list[SellToBuyChurnAuditResponse] = []
    for ticker, ticker_rows in by_ticker.items():
        prev_type: str | None = None
        for row in ticker_rows:
            if row.decision_type == "buy" and prev_type == "sell":
                items.append(
                    SellToBuyChurnAuditResponse(
                        ticker=ticker,
                        decision_ts=row.decision_ts,
                        decision_type=row.decision_type,
                        prev_type=prev_type,
                    )
                )
            prev_type = row.decision_type
    items.sort(key=lambda row: (row.ticker, row.decision_ts))
    return items


@router.get("/analytics/decision-events/market-validation", response_model=DecisionMarketValidationPageResponse)
@track_tables("decision_events", "second_aggregates")
def analytics_decision_events_market_validation(
    trade_date: date | None = None,
    reason_code: str | None = None,
    ticker: str | None = None,
    page: int = 0,
    page_size: int = 50,
    db: Session = Depends(get_db),
):
    target_trade_date = trade_date or _default_decision_trade_day()
    current_page = max(0, page)
    current_page_size = max(1, page_size)

    sell_query = _decision_sell_query(
        db,
        trade_date=target_trade_date,
        reason_code=reason_code,
        ticker=ticker,
    )
    total = sell_query.count()

    buys_by_ticker: dict[str, list[DecisionEvent]] = {}
    for row in _decision_buy_rows(db, trade_date=target_trade_date, ticker=ticker):
        buys_by_ticker.setdefault(row.ticker, []).append(row)

    paged_sells = (
        sell_query.order_by(DecisionEvent.decision_ts.asc(), DecisionEvent.ticker.asc(), DecisionEvent.id.asc())
        .offset(current_page * current_page_size)
        .limit(current_page_size)
        .all()
    )
    page_rows = _build_market_validation_rows(db, sells=paged_sells, buys_by_ticker=buys_by_ticker)
    items = [DecisionMarketValidationRowResponse(**row) for row in page_rows]

    summary_rows = _build_market_validation_rows(
        db,
        sells=(
            sell_query.order_by(DecisionEvent.decision_ts.asc(), DecisionEvent.ticker.asc(), DecisionEvent.id.asc()).all()
        ),
        buys_by_ticker=buys_by_ticker,
    )
    summary = Counter(row["match_status"] for row in summary_rows)
    summary["total"] = total
    return DecisionMarketValidationPageResponse(
        trade_date=target_trade_date,
        total=total,
        page=current_page,
        page_size=current_page_size,
        summary=dict(summary),
        items=items,
    )
