from datetime import datetime

from pydantic import BaseModel

from app.models.signal import SignalType


class SignalBase(BaseModel):
    ticker: str
    signal_type: SignalType
    score: float
    liquidity_imbalance: float | None = None
    spread_compression: float | None = None
    bid_stacking: float | None = None
    volume_acceleration: float | None = None
    order_aggression: float | None = None


class SignalCreate(SignalBase):
    pass


class SignalRead(SignalBase):
    id: int
    ml_confidence: float | None = None
    acted_on: bool
    outcome_pnl: float | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
