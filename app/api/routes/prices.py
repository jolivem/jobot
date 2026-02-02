from fastapi import APIRouter, Depends
from app.api.deps import get_current_user
from app.services.binance_price_service import BinancePriceService

router = APIRouter(prefix="/prices", tags=["prices"])

@router.get("/{symbol}")
def get_price(symbol: str, user = Depends(get_current_user)):
    price = BinancePriceService().get_price(symbol)
    return {"symbol": symbol.upper(), "price": price}
