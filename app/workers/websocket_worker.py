#!/usr/bin/env python3
"""
Binance WebSocket Worker

Standalone worker that maintains a persistent WebSocket connection to Binance
and caches real-time price updates in Redis.

Usage:
    python -m app.workers.websocket_worker

    # Or with Docker:
    docker compose up websocket-worker
"""

import asyncio
import logging
import signal
import sys
from typing import Set

from app.core.db import SessionLocal
from app.core.logging import setup_logging
from app.repositories.trading_bot_repo import TradingBotRepository
from app.services.binance_websocket_service import BinanceWebSocketService

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


class WebSocketWorker:
    """Manages the WebSocket connection and symbol tracking"""

    def __init__(self):
        self.ws_service = BinanceWebSocketService()
        self.is_running = False
        self.symbol_refresh_interval = 60  # Refresh symbols every 60 seconds

    async def refresh_symbols(self) -> Set[str]:
        """Fetch active trading bot symbols from database"""
        db = SessionLocal()
        try:
            repo = TradingBotRepository(db)
            symbols = repo.list_active_symbols()
            logger.info(f"Refreshed symbols from database: {len(symbols)} active symbols")
            return set(symbols)
        except Exception as e:
            logger.error(f"Error refreshing symbols: {e}", exc_info=True)
            return set()
        finally:
            db.close()

    async def periodic_symbol_refresh(self):
        """Periodically refresh the list of symbols to track"""
        while self.is_running:
            try:
                symbols = await self.refresh_symbols()
                if symbols:
                    self.ws_service.set_symbols_to_track(symbols)
                else:
                    logger.warning("No active trading bots found. WebSocket will cache all symbols.")
                    # Set to None to cache all symbols
                    self.ws_service.set_symbols_to_track(None)

            except Exception as e:
                logger.error(f"Error in periodic symbol refresh: {e}", exc_info=True)

            await asyncio.sleep(self.symbol_refresh_interval)

    async def run(self):
        """Main worker loop"""
        self.is_running = True
        logger.info("Starting Binance WebSocket Worker...")

        # Initial symbol load
        symbols = await self.refresh_symbols()
        if symbols:
            self.ws_service.set_symbols_to_track(symbols)
        else:
            logger.warning("No active trading bots found. Starting WebSocket anyway (will cache all symbols).")

        # Start both tasks concurrently
        try:
            await asyncio.gather(
                self.ws_service.connect_and_stream(),
                self.periodic_symbol_refresh(),
                return_exceptions=True
            )
        except Exception as e:
            logger.error(f"Fatal error in worker: {e}", exc_info=True)
        finally:
            await self.stop()

    async def stop(self):
        """Graceful shutdown"""
        logger.info("Stopping WebSocket Worker...")
        self.is_running = False
        await self.ws_service.stop()
        logger.info("WebSocket Worker stopped")


# Global worker instance for signal handling
worker = None


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info(f"Received signal {signum}. Initiating graceful shutdown...")
    if worker:
        asyncio.create_task(worker.stop())
    sys.exit(0)


async def main():
    """Entry point"""
    global worker

    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    worker = WebSocketWorker()

    try:
        await worker.run()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        await worker.stop()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        await worker.stop()
        sys.exit(1)


if __name__ == "__main__":
    # Run the async main function
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
        sys.exit(0)
