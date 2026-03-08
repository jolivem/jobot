import time
from sqlalchemy.orm import Session
from app.workers.celery_app import celery
from app.core.db import SessionLocal
from app.repositories.trading_bot_repo import TradingBotRepository
from app.repositories.trade_repo import TradeRepository
from app.services.binance_price_service import BinancePriceService
from app.services.binance_trade_service import BinanceTradeService
from app.services.trading_strategy import decide_trade, reconstruct_state_from_trades
from app.core.cache import RedisCache
from app.core.config import settings
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
    """Long-running task for a single trading bot.

    Loops every second, reads price from Redis, runs the grid trading strategy,
    and records trades in the database. When BINANCE_LIVE_TRADING is enabled
    and the user has API credentials, real orders are placed on Binance.
    """
    logger.info(f"Starting trading bot task for bot_id={bot_id}")
    cache = RedisCache()
    iteration = 0
    db_check_interval = 30
    previous_price = None

    # Resolve Binance trade service for live trading
    binance_service = None
    if settings.BINANCE_LIVE_TRADING:
        db_user: Session = SessionLocal()
        try:
            user = TradingBotRepository(db_user).get_user_for_bot(bot_id)
            if user and user.binance_api_key and user.binance_api_secret:
                api_key = decrypt(user.binance_api_key)
                api_secret = decrypt(user.binance_api_secret)
                binance_service = BinanceTradeService(api_key, api_secret)
                logger.info(f"Bot {bot_id}: live trading enabled")
            else:
                logger.warning(f"Bot {bot_id}: BINANCE_LIVE_TRADING=true but user has no API credentials, running in simulation")
        finally:
            db_user.close()

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

            # Execute and record each decision
            if decisions:
                trade_repo = TradeRepository(db)
                for decision in decisions:
                    filled_price = decision["entry_price"]
                    filled_qty = decision["quantity"]

                    # Place real order on Binance if live trading is enabled
                    if binance_service:
                        try:
                            result = binance_service.place_order(
                                bot.symbol, decision["side"].upper(), decision["quantity"]
                            )
                            # Use actual filled price/qty from Binance response
                            fills = result.get("fills", [])
                            if fills:
                                total_qty = sum(float(f["qty"]) for f in fills)
                                total_cost = sum(float(f["qty"]) * float(f["price"]) for f in fills)
                                filled_price = total_cost / total_qty if total_qty > 0 else filled_price
                                filled_qty = total_qty
                            logger.info(f"Bot {bot_id}: {decision['side']} {filled_qty} {bot.symbol} @ {filled_price}")
                        except Exception as e:
                            logger.error(f"Bot {bot_id}: Binance order failed: {e}", exc_info=True)
                            continue  # Skip recording if real order failed

                    trade_repo.create(
                        trading_bot_id=bot_id,
                        trade_type=decision["side"],
                        price=filled_price,
                        quantity=filled_qty,
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
