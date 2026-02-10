import time
from sqlalchemy.orm import Session
from app.workers.celery_app import celery
from app.core.db import SessionLocal
from app.repositories.trading_bot_repo import TradingBotRepository
from app.repositories.trade_repo import TradeRepository
from app.services.binance_price_service import BinancePriceService
from app.services.trading_strategy import decide_trade, reconstruct_state_from_trades
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
            return

        # Fetch prices from Binance
        binance = BinancePriceService()
        prices = binance.get_prices_batch(symbols)

        # Store in Redis
        cache = RedisCache()
        cache.set_prices_batch(prices)

    except Exception as e:
        logger.error(f"Error caching prices: {e}", exc_info=True)
    finally:
        db.close()


@celery.task(name="app.workers.tasks.restart_active_bots")
def restart_active_bots():
    """Restart trading bot tasks for all active bots in DB."""
    db: Session = SessionLocal()
    try:
        bot_repo = TradingBotRepository(db)
        bot_ids = bot_repo.list_active_ids()
        if not bot_ids:
            logger.info("No active bots to restart")
            return
        for bot_id in bot_ids:
            run_trading_bot.delay(bot_id)
            logger.info(f"Restarted trading bot task for bot_id={bot_id}")
        logger.info(f"Restarted {len(bot_ids)} active bot(s)")
    except Exception as e:
        logger.error(f"Error restarting active bots: {e}", exc_info=True)
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

    default_state = {
        "positions": [], "lowest_price": None,
        "grid_prices": [], "next_grid_index": 0,
    }

    # Load bot state from Redis, or reconstruct from DB trades
    state = cache.get_bot_state(bot_id)
    if state is None:
        db_init: Session = SessionLocal()
        try:
            bot_repo_init = TradingBotRepository(db_init)
            bot_init = bot_repo_init.get_active_by_id(bot_id)
            if bot_init:
                trades = TradeRepository(db_init).list_by_bot(bot_id)
                if trades:
                    state = reconstruct_state_from_trades(bot_init, trades)
                    cache.set_bot_state(bot_id, state)
                else:
                    state = dict(default_state)
            else:
                state = dict(default_state)
        except Exception as e:
            logger.error(f"Bot {bot_id}: error reconstructing state: {e}", exc_info=True)
            state = dict(default_state)
        finally:
            db_init.close()

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
                if iteration % 30 == 0:
                    logger.warning(f"Bot {bot_id}: no price in Redis for {bot.symbol}, waiting...")
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

            # Persist updated state to Redis every tick
            cache.set_bot_state(bot_id, state)

            previous_price = price

        except Exception as e:
            logger.error(f"Bot {bot_id}: unexpected error: {e}", exc_info=True)
        finally:
            db.close()

        iteration += 1
        time.sleep(1)
