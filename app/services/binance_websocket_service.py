import asyncio
import json
import logging
from typing import Set, Callable, Optional
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException
from app.core.config import settings
from app.core.cache import RedisCache

logger = logging.getLogger(__name__)


class BinanceWebSocketService:
    """Real-time price streaming via Binance WebSocket

    Streams all market tickers from Binance and caches prices in Redis.
    Features:
    - Automatic reconnection on disconnect
    - Filters to only cache symbols we care about
    - Heartbeat/keepalive handling
    - Error resilience
    """

    def __init__(self):
        # Use Binance stream endpoint for all market tickers
        # This receives updates for ALL symbols (~1-2 updates per second per active symbol)
        self.ws_url = "wss://stream.binance.com:9443/ws/!ticker@arr"
        self.cache = RedisCache()
        self.symbols_to_track: Optional[Set[str]] = None
        self.reconnect_delay = 5  # seconds
        self.max_reconnect_delay = 60  # max backoff
        self.is_running = False

    def set_symbols_to_track(self, symbols: Optional[Set[str]]):
        """Set which symbols to cache (None = cache all symbols)"""
        if symbols is None:
            self.symbols_to_track = None
            logger.info("Tracking ALL symbols (no filter)")
        else:
            self.symbols_to_track = {s.upper() for s in symbols}
            logger.info(f"Tracking {len(self.symbols_to_track)} symbols: {self.symbols_to_track}")

    async def connect_and_stream(self):
        """Main streaming loop with automatic reconnection"""
        current_delay = self.reconnect_delay
        self.is_running = True

        while self.is_running:
            try:
                logger.info(f"Connecting to Binance WebSocket: {self.ws_url}")
                async with websockets.connect(
                    self.ws_url,
                    ping_interval=20,  # Send ping every 20 seconds
                    ping_timeout=10,   # Wait 10 seconds for pong
                    close_timeout=10
                ) as websocket:
                    logger.info("WebSocket connected successfully")
                    current_delay = self.reconnect_delay  # Reset backoff on successful connection

                    await self._stream_messages(websocket)

            except ConnectionClosed as e:
                logger.warning(f"WebSocket connection closed: {e}. Reconnecting in {current_delay}s...")
                await asyncio.sleep(current_delay)
                current_delay = min(current_delay * 2, self.max_reconnect_delay)

            except WebSocketException as e:
                logger.error(f"WebSocket error: {e}. Reconnecting in {current_delay}s...")
                await asyncio.sleep(current_delay)
                current_delay = min(current_delay * 2, self.max_reconnect_delay)

            except Exception as e:
                logger.error(f"Unexpected error in WebSocket stream: {e}", exc_info=True)
                await asyncio.sleep(current_delay)
                current_delay = min(current_delay * 2, self.max_reconnect_delay)

        logger.info("WebSocket service stopped")

    async def _stream_messages(self, websocket):
        """Process incoming messages from WebSocket"""
        message_count = 0

        async for message in websocket:
            try:
                # Parse message - Binance sends array of ticker objects
                tickers = json.loads(message)

                if not isinstance(tickers, list):
                    logger.warning(f"Unexpected message format: {type(tickers)}")
                    continue

                # Filter and extract prices
                prices = {}
                for ticker in tickers:
                    symbol = ticker.get('s')  # Symbol (e.g., 'BTCUSDT')
                    price = ticker.get('c')   # Current close price

                    if symbol and price:
                        # Only cache symbols we're tracking (if filter is set)
                        if self.symbols_to_track is None or symbol in self.symbols_to_track:
                            prices[symbol] = float(price)

                # Batch update Redis
                if prices:
                    self.cache.set_prices_batch(prices, ttl=10)  # 10s TTL for safety

                    message_count += 1
                    if message_count % 10 == 0:  # Log every 10 updates
                        logger.debug(f"Cached {len(prices)} prices (total messages: {message_count})")

            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode JSON message: {e}")
                continue

            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                continue

    async def stop(self):
        """Stop the WebSocket service gracefully"""
        logger.info("Stopping WebSocket service...")
        self.is_running = False


class BinanceSymbolWebSocketService:
    """WebSocket service for specific symbols (alternative implementation)

    Use this if you want to stream only specific symbols instead of all tickers.
    More efficient for small number of symbols (<10).
    """

    def __init__(self, symbols: list[str]):
        self.symbols = [s.lower() for s in symbols]
        # Combined streams endpoint
        streams = "/".join([f"{s}@ticker" for s in self.symbols])
        self.ws_url = f"wss://stream.binance.com:9443/stream?streams={streams}"
        self.cache = RedisCache()
        self.is_running = False

    async def connect_and_stream(self):
        """Stream specific symbols"""
        self.is_running = True

        while self.is_running:
            try:
                logger.info(f"Connecting to Binance WebSocket for symbols: {self.symbols}")
                async with websockets.connect(
                    self.ws_url,
                    ping_interval=20,
                    ping_timeout=10
                ) as websocket:
                    logger.info("WebSocket connected")

                    async for message in websocket:
                        try:
                            data = json.loads(message)

                            # Extract ticker data from stream format
                            ticker = data.get('data', {})
                            symbol = ticker.get('s')
                            price = ticker.get('c')

                            if symbol and price:
                                self.cache.set_price(symbol, float(price), ttl=10)

                        except Exception as e:
                            logger.error(f"Error processing message: {e}")
                            continue

            except Exception as e:
                logger.error(f"WebSocket error: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)

    async def stop(self):
        """Stop streaming"""
        self.is_running = False
