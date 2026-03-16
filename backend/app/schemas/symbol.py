from datetime import datetime

from pydantic import BaseModel


class SymbolBase(BaseModel):
    ticker: str
    name: str = ""
    exchange: str = "NASDAQ"
    last_price: float | None = None
    avg_volume: int | None = None
    is_active: bool = True


class SymbolCreate(SymbolBase):
    pass


class SymbolRead(SymbolBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
