from pydantic import BaseModel, Field

class PortfolioUpsert(BaseModel):
    symbol: str = Field(..., examples=["BTCUSDT"])
    quantity: float = Field(..., ge=0)

class PortfolioRead(BaseModel):
    id: int
    symbol: str
    quantity: float

    class Config:
        from_attributes = True
