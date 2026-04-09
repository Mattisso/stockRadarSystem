"""Pydantic schemas for ML, analytics, and Secret Sauce ops endpoints."""

from datetime import date, datetime

from pydantic import BaseModel


class MLStatusResponse(BaseModel):
    model_trained: bool
    feature_importances: dict[str, float] | None = None
    ml_enabled: bool
    ml_confidence_weight: float
    min_training_samples: int


class RetrainResponse(BaseModel):
    status: str  # "retrained" | "insufficient_data" | "error"
    samples: int | None = None
    metrics: dict | None = None


class BacktestRequest(BaseModel):
    start_date: datetime | None = None
    end_date: datetime | None = None
    slippage_pct: float = 0.001
    commission_per_share: float = 0.005
    initial_capital: float = 50_000.0
    max_position_size: float = 5_000.0
    score_threshold: float = 0.65


class BacktestResponse(BaseModel):
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_pnl: float
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    max_drawdown: float
    sharpe_ratio: float
    trades: list[dict]


class KPIResponse(BaseModel):
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_pnl: float
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    sharpe_ratio: float
    avg_hold_time_minutes: float
    days: int


class SignalAccuracyBucketResponse(BaseModel):
    range: str
    total: int
    wins: int
    win_rate: float
    average_pnl: float
    expectancy: float


class ApiContractResponse(BaseModel):
    rest_base: str
    websocket_base: str
    auth_token_path: str
    websocket_auth: str
    public_routes: list[str]
    protected_routes: list[str]
    websocket_channels: list[str]


class SecretSauceContractResponse(BaseModel):
    consumer: str
    handoff_route: str
    handoff_fields: list[str]
    promotion_reason: str
    requires_l2: bool


class SecretSauceHandoffResponse(BaseModel):
    ticker: str
    score: float
    detected_at: datetime
    price_velocity_1m: float
    volume_expansion: float
    spread_pct: float
    quote_rate: float
    buy_pressure: float
    reason_flags: list[str]
    promotion_reason: str
    consumer: str
    l2_required: bool


class SecretSauceQueueStatusResponse(BaseModel):
    active_count: int
    active_tickers: list[str]
    queue_depth: int
    queued_tickers: list[str]
    max_active: int
    max_queue_size: int
    replaceable_tickers: list[str]


class SecretSauceStatusResponse(BaseModel):
    runtime: dict
    queue: SecretSauceQueueStatusResponse
    polygon_session: dict | None = None


class SecretReplayQuoteRequest(BaseModel):
    ticker: str
    bid: float
    ask: float
    last: float
    volume: int
    timestamp: datetime


class SecretReplayRequest(BaseModel):
    quotes: list[SecretReplayQuoteRequest]


class SecretReplaySnapshotResponse(BaseModel):
    ticker: str
    price_velocity_1m: float
    spread_pct: float
    quote_rate: float
    volume_expansion: float
    buy_pressure: float
    last_price: float
    last_updated: datetime


class SecretReplayCandidateResponse(BaseModel):
    ticker: str
    score: float
    price_velocity_1m: float
    pct_change_5m: float
    volume_expansion: float
    spread_pct: float
    quote_rate: float
    buy_pressure: float
    reason_flags: list[str]
    timestamp: datetime


class SecretReplayResponse(BaseModel):
    snapshots: list[SecretReplaySnapshotResponse]
    candidates: list[SecretReplayCandidateResponse]
    handoffs: list[SecretSauceHandoffResponse]
    queue: SecretSauceQueueStatusResponse
    promoted_tickers: list[str]


class SecretUniverseDailyResponse(BaseModel):
    id: int
    trade_date: date
    ticker: str
    exchange: str
    open_price: float | None = None
    prev_close: float | None = None
    last_price: float | None = None
    avg_volume: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SecretL1CandidateResponse(BaseModel):
    id: int
    ticker: str
    detected_at: datetime
    breakout_score: float
    price: float | None = None
    pct_change_1m: float | None = None
    pct_change_5m: float | None = None
    volume_ratio: float | None = None
    reason_flags: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SecretL1ToL2EventResponse(BaseModel):
    id: int
    ticker: str
    detect_ts: datetime
    escalate_ts: datetime
    latency_ms: float | None = None
    slot_id: str | None = None
    escalation_reason: str | None = None
    handoff_payload: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SecretSauceReasonCountResponse(BaseModel):
    label: str
    count: int


class SecretSauceLatencySummaryResponse(BaseModel):
    count: int
    avg_ms: float | None = None
    median_ms: float | None = None
    p95_ms: float | None = None


class SecretSauceFunnelResponse(BaseModel):
    trade_date: date | None = None
    universe_count: int
    candidate_count: int
    handoff_count: int
    candidate_conversion_pct: float
    handoff_conversion_pct: float
    universe_to_handoff_pct: float
    latency: SecretSauceLatencySummaryResponse
    top_reason_flags: list[SecretSauceReasonCountResponse]
    top_escalation_reasons: list[SecretSauceReasonCountResponse]


class PolygonDayAggregateResponse(BaseModel):
    id: int
    trade_date: date
    ticker: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: float | None = None
    transactions: int | None = None
    source_ts: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PolygonMinuteAggregateResponse(BaseModel):
    id: int
    ticker: str
    minute_ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: float | None = None
    transactions: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PolygonSecondAggregateResponse(BaseModel):
    id: int
    ticker: str
    second_ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: float | None = None
    transactions: int | None = None


class PolygonTickResponse(BaseModel):
    id: int
    ticker: str
    event_type: str
    bid: float
    ask: float
    last: float
    volume: int
    tick_ts: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class PolygonDayAggregatePageResponse(BaseModel):
    items: list[PolygonDayAggregateResponse]
    total: int
    page: int
    page_size: int
    trade_date: date | None = None


class PolygonMinuteAggregatePageResponse(BaseModel):
    items: list[PolygonMinuteAggregateResponse]
    total: int
    page: int
    page_size: int
    trade_date: date | None = None


class PolygonSecondAggregatePageResponse(BaseModel):
    items: list[PolygonSecondAggregateResponse]
    total: int
    page: int
    page_size: int
    trade_date: date | None = None


class PolygonTickPageResponse(BaseModel):
    items: list[PolygonTickResponse]
    total: int
    page: int
    page_size: int
    trade_date: date | None = None


class L2SubscriptionStatusResponse(BaseModel):
    ticker: str
    confirmed: bool
    has_depth: bool
    bid_levels: int
    ask_levels: int
    last_updated_at: float | None = None


class L2HealthResponse(BaseModel):
    active_count: int
    books_with_depth_count: int
    subscribed_tickers: list[str]
    subscriptions: list[L2SubscriptionStatusResponse]
