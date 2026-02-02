from fastapi import APIRouter, Depends
from app.api.deps import require_admin
from app.services.binance_price_service import BinancePriceService

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/price/{symbol}")
def admin_price(symbol: str, admin = Depends(require_admin)):
    price = BinancePriceService().get_price(symbol)
    return {"symbol": symbol.upper(), "price": price}
