import time
from sqlalchemy.orm import Session
from app.workers.celery_app import celery
from app.core.db import SessionLocal
from app.repositories.trading_bot_repo import TradingBotRepository
from app.repositories.trade_repo import TradeRepository
from app.services.binance_price_service import BinancePriceService
from app.services.binance_trade_service import BinanceTradeService
from app.services.trading_strategy import decide_trade
from app.core.cache import RedisCache
from app.core.encryption import decrypt
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


@celery.task(name="app.workers.tasks.run_trading_bot", bind=True)
def run_trading_bot(self, bot_id: int):
    """Long-running task for a single trading bot.

    Loops every second, reads price from Redis, runs the trading strategy,
    and executes trades on Binance if needed. Stops when the bot is
    deactivated in DB.
    """
    logger.info(f"Starting trading bot task for bot_id={bot_id}")
    cache = RedisCache()
    iteration = 0
    db_check_interval = 30  # Re-check bot status in DB every 30 iterations

    while True:
        db: Session = SessionLocal()
        try:
            bot_repo = TradingBotRepository(db)

            # Periodically verify bot is still active
            if iteration % db_check_interval == 0:
                bot = bot_repo.get_active_by_id(bot_id)
                if not bot:
                    logger.info(f"Bot {bot_id} is no longer active, stopping task")
                    return

            # Read price from Redis
            bot = bot_repo.get_active_by_id(bot_id)
            if not bot:
                logger.info(f"Bot {bot_id} not found or inactive, stopping task")
                return

            price = cache.get_price(bot.symbol)
            if price is None:
                iteration += 1
                time.sleep(1)
                continue

            # Run trading strategy
            decision = decide_trade(bot, price)
            if decision is None:
                iteration += 1
                time.sleep(1)
                continue

            side = decision["side"]
            quantity = decision["quantity"]

            # Get user's Binance API keys
            user = bot_repo.get_user_for_bot(bot_id)
            if not user or not user.binance_api_key or not user.binance_api_secret:
                logger.warning(f"Bot {bot_id}: user has no Binance API keys configured, skipping trade")
                iteration += 1
                time.sleep(1)
                continue

            # Execute trade on Binance (decrypt API keys)
            try:
                api_key = decrypt(user.binance_api_key)
                api_secret = decrypt(user.binance_api_secret)
                trade_service = BinanceTradeService(api_key, api_secret)
                trade_service.place_order(bot.symbol, side.upper(), quantity)
            except Exception as e:
                logger.error(f"Bot {bot_id}: failed to execute {side} order: {e}")
                iteration += 1
                time.sleep(1)
                continue

            # Record trade in DB
            trade_repo = TradeRepository(db)
            trade_repo.create(
                trading_bot_id=bot_id,
                trade_type=side,
                price=price,
                quantity=quantity,
            )
            logger.info(f"Bot {bot_id}: executed {side} {quantity} {bot.symbol} @ {price}")

        except Exception as e:
            logger.error(f"Bot {bot_id}: unexpected error: {e}", exc_info=True)
        finally:
            db.close()

        iteration += 1
        time.sleep(1)
