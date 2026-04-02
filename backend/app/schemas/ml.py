"""Pydantic schemas for ML and analytics endpoints."""

from datetime import datetime

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
