from fastapi import APIRouter
from app.services.binance_price_service import BinancePriceService
from app.core.cache import RedisCache

router = APIRouter(prefix="/symbols", tags=["symbols"])


@router.get("/usdc")
def get_usdc_symbols():
    """Return all actively trading USDC pairs from Binance (cached 1h)."""
    cache = RedisCache()

    cached = cache.get_symbols("USDC")
    if cached is not None:
        return {"symbols": cached}

    symbols = BinancePriceService().get_usdc_symbols()
    cache.set_symbols("USDC", symbols, ttl=3600)

    return {"symbols": symbols}
