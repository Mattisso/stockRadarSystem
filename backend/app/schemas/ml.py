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
