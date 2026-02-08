import redis
import json
import time
from typing import Optional
from app.core.config import settings


class RedisCache:
    """Redis client for caching cryptocurrency prices"""

    def __init__(self):
        self.client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2
        )

    def set_price(self, symbol: str, price: float, ttl: int = 5) -> None:
        """Store a single price in cache with TTL

        Args:
            symbol: Cryptocurrency symbol (e.g., 'BTCUSDT')
            price: Current price
            ttl: Time-to-live in seconds (default: 5)
        """
        key = f"price:{symbol.upper()}"
        data = {
            "price": price,
            "timestamp": time.time(),
            "source": "binance"
        }
        self.client.setex(key, ttl, json.dumps(data))

    def get_price(self, symbol: str) -> Optional[float]:
        """Retrieve price from cache

        Args:
            symbol: Cryptocurrency symbol (e.g., 'BTCUSDT')

        Returns:
            Price as float or None if not found/expired
        """
        key = f"price:{symbol.upper()}"
        data = self.client.get(key)
        if not data:
            return None
        return float(json.loads(data)["price"])

    def set_prices_batch(self, prices: dict[str, float], ttl: int = 5) -> None:
        """Store multiple prices atomically using pipeline

        Args:
            prices: Dictionary mapping symbol to price
            ttl: Time-to-live in seconds (default: 5)
        """
        if not prices:
            return

        pipe = self.client.pipeline()
        timestamp = time.time()

        for symbol, price in prices.items():
            key = f"price:{symbol.upper()}"
            data = {
                "price": price,
                "timestamp": timestamp,
                "source": "binance"
            }
            pipe.setex(key, ttl, json.dumps(data))

        pipe.execute()

    def set_symbols(self, quote_asset: str, symbols: list[str], ttl: int = 3600) -> None:
        """Cache a list of trading symbols for a given quote asset."""
        key = f"symbols:{quote_asset.upper()}"
        self.client.setex(key, ttl, json.dumps(symbols))

    def get_symbols(self, quote_asset: str) -> Optional[list[str]]:
        """Retrieve cached symbols for a quote asset."""
        key = f"symbols:{quote_asset.upper()}"
        data = self.client.get(key)
        if not data:
            return None
        return json.loads(data)

    def set_bot_state(self, bot_id: int, state: dict) -> None:
        """Store trading bot runtime state (positions, lowest_price, etc.)."""
        key = f"bot_state:{bot_id}"
        self.client.set(key, json.dumps(state))

    def get_bot_state(self, bot_id: int) -> Optional[dict]:
        """Retrieve trading bot runtime state."""
        key = f"bot_state:{bot_id}"
        data = self.client.get(key)
        if not data:
            return None
        return json.loads(data)

    def delete_bot_state(self, bot_id: int) -> None:
        """Remove trading bot runtime state."""
        key = f"bot_state:{bot_id}"
        self.client.delete(key)
