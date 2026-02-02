from pydantic import BaseModel

class PriceResponse(BaseModel):
    symbol: str
    price: float
