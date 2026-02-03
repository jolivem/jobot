from pydantic import BaseModel, Field

class AlertCreate(BaseModel):
    symbol: str = Field(..., examples=["BTCUSDT"])
    target_price: float = Field(..., gt=0)
    direction: str = Field(..., examples=["above", "below"])

class AlertRead(BaseModel):
    id: int
    symbol: str
    target_price: float
    direction: str
    is_active: int

    class Config:
        from_attributes = True

class AlertEventRead(BaseModel):
    id: int
    alert_id: int
    user_id: int
    symbol: str
    triggered_price: float

    class Config:
        from_attributes = True
