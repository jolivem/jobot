from datetime import datetime
from pydantic import BaseModel


class TradeRead(BaseModel):
    id: int
    trading_bot_id: int
    trade_type: str
    price: float
    quantity: float
    created_at: datetime

    class Config:
        from_attributes = True
