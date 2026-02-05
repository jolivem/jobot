import hashlib
import hmac
import time
import logging
from urllib.parse import urlencode

import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


class BinanceTradeService:
    """Authenticated Binance API client for placing orders.

    Uses the user's own API key and secret to execute trades.
    """

    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = settings.BINANCE_BASE_URL.rstrip("/")
        self.client = httpx.Client(timeout=10.0)

    def _sign(self, params: dict) -> str:
        query = urlencode(params)
        return hmac.new(
            self.api_secret.encode(),
            query.encode(),
            hashlib.sha256,
        ).hexdigest()

    def place_order(self, symbol: str, side: str, quantity: float) -> dict:
        """Place a market order on Binance.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            side: "BUY" or "SELL"
            quantity: Amount to trade

        Returns:
            Binance order response dict

        Raises:
            httpx.HTTPStatusError: On API error
            ValueError: If live trading is disabled
        """
        if not settings.BINANCE_LIVE_TRADING:
            raise ValueError("Live trading is disabled (BINANCE_LIVE_TRADING=false)")

        params = {
            "symbol": symbol.upper().strip(),
            "side": side.upper(),
            "type": "MARKET",
            "quantity": f"{quantity}",
            "timestamp": int(time.time() * 1000),
        }
        params["signature"] = self._sign(params)

        headers = {"X-MBX-APIKEY": self.api_key}

        r = self.client.post(
            f"{self.base_url}/api/v3/order",
            params=params,
            headers=headers,
        )
        r.raise_for_status()

        result = r.json()
        logger.info(f"Order executed: {side} {quantity} {symbol} - orderId={result.get('orderId')}")
        return result
