import httpx
from app.core.config import settings

class BinancePriceService:
    """Public endpoints only: no API keys needed."""
    def __init__(self):
        self.base_url = settings.BINANCE_BASE_URL.rstrip("/")
        self.client = httpx.Client(timeout=10.0)

    def get_price(self, symbol: str) -> float:
        r = self.client.get(f"{self.base_url}/api/v3/ticker/price", params={"symbol": symbol.upper().strip()})
        r.raise_for_status()
        return float(r.json()["price"])
