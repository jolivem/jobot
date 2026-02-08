import time
from sqlalchemy.orm import Session
from app.workers.celery_app import celery
from app.core.db import SessionLocal
from app.repositories.trading_bot_repo import TradingBotRepository
from app.repositories.trade_repo import TradeRepository
from app.services.binance_price_service import BinancePriceService
from app.services.trading_strategy import decide_trade
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


@celery.task(name="app.workers.tasks.run_trading_bot", bind=True)
def run_trading_bot(self, bot_id: int):
    """Long-running task for a single trading bot (simulated mode).

    Loops every second, reads price from Redis, runs the grid trading strategy,
    and records simulated trades in the database. No real orders are placed.
    """
    logger.info(f"Starting trading bot task for bot_id={bot_id}")
    cache = RedisCache()
    iteration = 0
    db_check_interval = 30
    previous_price = None

    # Load or initialize bot state from Redis
    state = cache.get_bot_state(bot_id) or {"positions": [], "lowest_price": None}

    while True:
        db: Session = SessionLocal()
        try:
            bot_repo = TradingBotRepository(db)

            # Periodically verify bot is still active
            if iteration % db_check_interval == 0:
                bot = bot_repo.get_active_by_id(bot_id)
                if not bot:
                    logger.info(f"Bot {bot_id} is no longer active, stopping task")
                    cache.delete_bot_state(bot_id)
                    return

            bot = bot_repo.get_active_by_id(bot_id)
            if not bot:
                logger.info(f"Bot {bot_id} not found or inactive, stopping task")
                cache.delete_bot_state(bot_id)
                return

            # Read price from Redis
            price = cache.get_price(bot.symbol)
            if price is None:
                iteration += 1
                time.sleep(1)
                continue

            # Run grid trading strategy
            decisions, state = decide_trade(bot, price, state, previous_price)

            # Record each decision in DB
            if decisions:
                trade_repo = TradeRepository(db)
                for decision in decisions:
                    trade_repo.create(
                        trading_bot_id=bot_id,
                        trade_type=decision["side"],
                        price=decision["entry_price"],
                        quantity=decision["quantity"],
                    )

                # Persist updated state to Redis
                cache.set_bot_state(bot_id, state)

            previous_price = price

        except Exception as e:
            logger.error(f"Bot {bot_id}: unexpected error: {e}", exc_info=True)
        finally:
            db.close()

        iteration += 1
        time.sleep(1)
