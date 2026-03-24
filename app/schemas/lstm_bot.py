from pydantic import BaseModel, Field


class LstmBotCreate(BaseModel):
    symbol: str = Field(..., examples=["BTCUSDC"])
    timeframes: str = Field(..., examples=["15m,1d,1w"])
    total_amount: float = Field(..., gt=0)
    max_positions: int = Field(3, ge=1, le=20)
    buy_slope_threshold: float = Field(0.0)
    sell_slope_threshold: float = Field(0.0)
    take_profit_pct: float = Field(2.0, ge=0.1, le=50.0)
    stop_loss_pct: float = Field(3.0, ge=0.1, le=50.0)


class LstmBotUpdate(BaseModel):
    symbol: str | None = None
    timeframes: str | None = None
    total_amount: float | None = Field(None, gt=0)
    max_positions: int | None = Field(None, ge=1, le=20)
    buy_slope_threshold: float | None = None
    sell_slope_threshold: float | None = None
    take_profit_pct: float | None = Field(None, ge=0.1, le=50.0)
    stop_loss_pct: float | None = Field(None, ge=0.1, le=50.0)
    is_active: int | None = Field(None, ge=0, le=1)


class LstmBotRead(BaseModel):
    id: int
    user_id: int
    symbol: str
    is_active: int
    timeframes: str
    total_amount: float
    max_positions: int
    buy_slope_threshold: float
    sell_slope_threshold: float
    take_profit_pct: float
    stop_loss_pct: float
    model_status: str

    class Config:
        from_attributes = True


class SlopeResponse(BaseModel):
    timeframe: str
    slope: float
    direction: str  # "up", "down", "neutral"
