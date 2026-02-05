from sqlalchemy.orm import Session
from app.workers.celery_app import celery
from app.core.db import SessionLocal
from app.repositories.alert_repo import AlertRepository
from app.repositories.trading_bot_repo import TradingBotRepository
from app.services.binance_price_service import BinancePriceService
from app.core.cache import RedisCache
import logging

logger = logging.getLogger(__name__)


@celery.task(name="app.workers.tasks.cache_prices")
def cache_prices():
    """Fetch prices for all active trading bot symbols and cache in Redis"""
    db: Session = SessionLocal()
    try:
        bot_repo = TradingBotRepository(db)
        symbols = bot_repo.list_active_symbols()

        if not symbols:
            logger.debug("No active trading bots, skipping price cache update")
            return

        logger.info(f"Caching prices for {len(symbols)} symbols: {symbols}")

        # Fetch prices from Binance
        binance = BinancePriceService()
        prices = binance.get_prices_batch(symbols)

        # Store in Redis
        cache = RedisCache()
        cache.set_prices_batch(prices)

        logger.info(f"Successfully cached {len(prices)} prices")

    except Exception as e:
        logger.error(f"Error caching prices: {e}", exc_info=True)
    finally:
        db.close()


@celery.task(name="app.workers.tasks.check_price_alerts")
def check_price_alerts():
    """Check price alerts using cached prices with fallback to direct API"""
    db: Session = SessionLocal()
    try:
        repo = AlertRepository(db)
        cache = RedisCache()
        binance = BinancePriceService()

        alerts = repo.list_active()
        for a in alerts:
            try:
                # Try cache first
                price = cache.get_price(a.symbol)

                # Fallback to direct API if cache miss
                if price is None:
                    logger.warning(f"Cache miss for {a.symbol}, falling back to Binance API")
                    price = binance.get_price(a.symbol)

            except Exception as e:
                logger.error(f"Error getting price for {a.symbol}: {e}")
                continue

            hit = (price >= a.target_price) if a.direction == "above" else (price <= a.target_price)
            if hit:
                repo.mark_triggered(a, price)

    finally:
        db.close()
