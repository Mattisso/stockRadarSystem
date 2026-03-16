from datetime import datetime

from pydantic import BaseModel

from app.models.trade import TradeSide, TradeStatus


class TradeBase(BaseModel):
    ticker: str
    side: TradeSide
    quantity: int
    entry_price: float | None = None
    stop_loss_price: float | None = None
    target_price: float | None = None
    signal_score: float | None = None


class TradeCreate(TradeBase):
    pass


class TradeRead(TradeBase):
    id: int
    status: TradeStatus
    exit_price: float | None = None
    pnl: float | None = None
    entry_time: datetime | None = None
    exit_time: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
