from pydantic import BaseModel, Field


class TradingBotCreate(BaseModel):
    symbol: str = Field(..., examples=["BTCUSDT"])
    max_price: float = Field(..., gt=0, description="Maximum price threshold")
    min_price: float = Field(..., gt=0, description="Minimum price threshold")
    total_amount: float = Field(..., gt=0, description="Total amount to trade")
    sell_percentage: float = Field(..., gt=0, le=100, description="Percentage increase before selling")
    buy_percentage: float = Field(..., gt=0, le=100, description="Percentage decrease before buying")


class TradingBotUpdate(BaseModel):
    symbol: str | None = Field(None, examples=["BTCUSDT"])
    max_price: float | None = Field(None, gt=0)
    min_price: float | None = Field(None, gt=0)
    total_amount: float | None = Field(None, gt=0)
    sell_percentage: float | None = Field(None, gt=0, le=100)
    buy_percentage: float | None = Field(None, gt=0, le=100)
    is_active: int | None = Field(None, ge=0, le=1)


class BotStats(BaseModel):
    bot_id: int
    symbol: str
    realized_profit: float
    open_positions_count: int
    open_positions_cost: float
    current_price: float | None
    open_positions_value: float | None


class TradingBotRead(BaseModel):
    id: int
    user_id: int
    symbol: str
    is_active: int
    max_price: float
    min_price: float
    total_amount: float
    sell_percentage: float
    buy_percentage: float

    class Config:
        from_attributes = True
