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

    def get_prices_batch(self, symbols: list[str]) -> dict[str, float]:
        """Fetch multiple prices in one API call

        Args:
            symbols: List of cryptocurrency symbols (e.g., ['BTCUSDT', 'ETHUSDT'])

        Returns:
            Dictionary mapping symbol to price
        """
        if not symbols:
            return {}

        # Fetch all prices from Binance (single API call)
        r = self.client.get(f"{self.base_url}/api/v3/ticker/price")
        r.raise_for_status()

        all_prices = r.json()
        symbols_upper = {s.upper().strip() for s in symbols}

        # Filter to only requested symbols
        result = {}
        for item in all_prices:
            if item["symbol"] in symbols_upper:
                result[item["symbol"]] = float(item["price"])

        return result
