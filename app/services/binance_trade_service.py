import hashlib
import hmac
import time
import math
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
        self._lot_size_cache: dict[str, dict] = {}

    def _sign(self, params: dict) -> str:
        query = urlencode(params)
        return hmac.new(
            self.api_secret.encode(),
            query.encode(),
            hashlib.sha256,
        ).hexdigest()

    def _get_lot_size(self, symbol: str) -> dict | None:
        """Fetch LOT_SIZE filter for a symbol (stepSize, minQty)."""
        symbol = symbol.upper().strip()
        if symbol in self._lot_size_cache:
            return self._lot_size_cache[symbol]

        try:
            r = self.client.get(
                f"{self.base_url}/api/v3/exchangeInfo",
                params={"symbol": symbol},
            )
            r.raise_for_status()
            for f in r.json().get("symbols", [{}])[0].get("filters", []):
                if f["filterType"] == "LOT_SIZE":
                    self._lot_size_cache[symbol] = f
                    return f
        except Exception as e:
            logger.warning(f"Failed to fetch LOT_SIZE for {symbol}: {e}")
        return None

    def _round_quantity(self, symbol: str, quantity: float) -> str:
        """Round quantity to Binance's stepSize for the symbol."""
        lot_size = self._get_lot_size(symbol)
        if lot_size:
            step_size = float(lot_size["stepSize"])
            # Floor to step size precision
            precision = max(0, round(-math.log10(step_size)))
            quantity = math.floor(quantity / step_size) * step_size
            return f"{quantity:.{precision}f}"
        # Fallback: 2 decimal places
        return f"{math.floor(quantity * 100) / 100:.2f}"

    def get_asset_balance(self, asset: str) -> float:
        """Get the free balance for an asset from Binance account."""
        params = {"timestamp": int(time.time() * 1000)}
        params["signature"] = self._sign(params)
        headers = {"X-MBX-APIKEY": self.api_key}

        r = self.client.get(
            f"{self.base_url}/api/v3/account",
            params=params,
            headers=headers,
        )
        r.raise_for_status()
        for b in r.json().get("balances", []):
            if b["asset"] == asset.upper():
                return float(b["free"])
        return 0.0

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

        rounded_qty = self._round_quantity(symbol, quantity)
        logger.info(f"Placing order: {side} {rounded_qty} {symbol} (raw qty: {quantity})")

        params = {
            "symbol": symbol.upper().strip(),
            "side": side.upper(),
            "type": "MARKET",
            "quantity": rounded_qty,
            "timestamp": int(time.time() * 1000),
        }
        params["signature"] = self._sign(params)

        headers = {"X-MBX-APIKEY": self.api_key}

        try:
            r = self.client.post(
                f"{self.base_url}/api/v3/order",
                params=params,
                headers=headers,
            )
        except httpx.HTTPError as e:
            logger.error(f"Binance request failed (network): {e}")
            raise

        if r.status_code != 200:
            logger.error(f"Binance API error {r.status_code} for {side} {rounded_qty} {symbol}: {r.text}")
            r.raise_for_status()

        result = r.json()
        logger.info(
            f"Order filled: {side} {rounded_qty} {symbol} - "
            f"orderId={result.get('orderId')}, status={result.get('status')}, "
            f"fills={len(result.get('fills', []))}"
        )
        return result
