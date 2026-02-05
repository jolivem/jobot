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
