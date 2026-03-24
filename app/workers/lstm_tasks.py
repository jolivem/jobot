import time
import logging
from sqlalchemy.orm import Session
from app.workers.celery_app import celery
from app.core.db import SessionLocal
from app.core.cache import RedisCache
from app.core.config import settings
from app.core.encryption import decrypt
from app.repositories.lstm_bot_repo import LstmBotRepository
from app.repositories.trade_repo import TradeRepository
from app.services.lstm_model_service import predict_slopes, fine_tune, has_model
from app.strategies.lstm_slope_strategy import decide_trade
from app.services.binance_trade_service import BinanceTradeService

logger = logging.getLogger(__name__)


@celery.task(name="app.workers.lstm_tasks.run_lstm_bot", bind=True)
def run_lstm_bot(self, bot_id: int):
    """Long-running task for an LSTM slope-based trading bot.

    Periodically predicts slopes for each configured timeframe,
    makes buy/sell decisions, and records trades.
    """
    logger.info(f"Starting LSTM bot task for bot_id={bot_id}")
    cache = RedisCache()
    iteration = 0
    db_check_interval = 30

    # Resolve Binance trade service for live trading
    binance_service = None
    if settings.BINANCE_LIVE_TRADING:
        db_user: Session = SessionLocal()
        try:
            user = LstmBotRepository(db_user).get_user_for_bot(bot_id)
            if user and user.binance_api_key and user.binance_api_secret:
                api_key = decrypt(user.binance_api_key)
                api_secret = decrypt(user.binance_api_secret)
                binance_service = BinanceTradeService(api_key, api_secret)
                logger.info(f"LSTM Bot {bot_id}: live trading enabled")
        finally:
            db_user.close()

    # Load state from Redis or initialize
    state_key = f"lstm_bot_state:{bot_id}"
    state = cache.redis.get(state_key)
    if state:
        import json
        state = json.loads(state)
    else:
        state = {"positions": []}

    # Prediction interval: don't predict every second, predict every N seconds
    # based on the shortest timeframe
    predict_interval = 60  # predict every 60 seconds by default

    while True:
        db: Session = SessionLocal()
        try:
            bot_repo = LstmBotRepository(db)

            # Periodically verify bot is still active
            if iteration % db_check_interval == 0:
                bot = bot_repo.get_active_by_id(bot_id)
                if not bot:
                    logger.info(f"LSTM Bot {bot_id} is no longer active, stopping task")
                    cache.redis.delete(state_key)
                    return

            # Only predict and trade at the prediction interval
            if iteration % predict_interval != 0:
                iteration += 1
                time.sleep(1)
                continue

            bot = bot_repo.get_active_by_id(bot_id)
            if not bot:
                logger.info(f"LSTM Bot {bot_id} not found or inactive, stopping task")
                cache.redis.delete(state_key)
                return

            # Check that models are ready
            if bot.model_status != "ready":
                if iteration % 300 == 0:
                    logger.warning(f"LSTM Bot {bot_id}: model not ready (status={bot.model_status})")
                iteration += 1
                time.sleep(1)
                continue

            # Read current price from Redis
            price = cache.get_price(bot.symbol)
            if price is None:
                if iteration % 30 == 0:
                    logger.warning(f"LSTM Bot {bot_id}: no price for {bot.symbol}")
                iteration += 1
                time.sleep(1)
                continue

            # Predict slopes for all timeframes
            timeframes = bot.timeframes.split(",")
            slopes = predict_slopes(bot.symbol, timeframes)

            # Run strategy
            decisions, state = decide_trade(bot, price, slopes, state)

            # Execute decisions
            if decisions:
                trade_repo = TradeRepository(db)
                for decision in decisions:
                    filled_price = decision["entry_price"]
                    filled_qty = decision["quantity"]

                    if binance_service:
                        try:
                            result = binance_service.place_order(
                                bot.symbol, decision["side"].upper(), decision["quantity"]
                            )
                            fills = result.get("fills", [])
                            if fills:
                                total_qty = sum(float(f["qty"]) for f in fills)
                                total_cost = sum(float(f["qty"]) * float(f["price"]) for f in fills)
                                filled_price = total_cost / total_qty if total_qty > 0 else filled_price
                                filled_qty = total_qty
                            logger.info(f"LSTM Bot {bot_id}: {decision['side']} {filled_qty} @ {filled_price}")
                        except Exception as e:
                            logger.error(f"LSTM Bot {bot_id}: Binance order failed: {e}", exc_info=True)
                            continue

                    matched_buy_id = None
                    if decision["side"] == "sell" and "buy_entry" in decision:
                        matched_buy = trade_repo.find_unmatched_buy(bot_id, decision["buy_entry"])
                        if matched_buy:
                            matched_buy_id = matched_buy.id

                    trade_repo.create(
                        trading_bot_id=bot_id,
                        trade_type=decision["side"],
                        price=filled_price,
                        quantity=filled_qty,
                        matched_buy_trade_id=matched_buy_id,
                    )

                    # Sync state with actual Binance fill
                    if binance_service and decision["side"] == "buy":
                        for pos in reversed(state.get("positions", [])):
                            if abs(pos["entry"] - decision["entry_price"]) < 1e-8:
                                pos["qty"] = filled_qty
                                pos["entry"] = filled_price
                                pos["fee"] = filled_qty * filled_price * settings.FEE_PCT
                                break

            # Save state to Redis
            import json
            cache.redis.set(state_key, json.dumps(state))

        except Exception as e:
            logger.error(f"LSTM Bot {bot_id}: unexpected error: {e}", exc_info=True)
        finally:
            db.close()

        iteration += 1
        time.sleep(1)


@celery.task(name="app.workers.lstm_tasks.update_lstm_models")
def update_lstm_models():
    """Periodic task: fine-tune LSTM models for all active bots with latest data."""
    db: Session = SessionLocal()
    try:
        bot_repo = LstmBotRepository(db)
        bot_ids = bot_repo.list_active_ids()

        for bot_id in bot_ids:
            bot = bot_repo.get_active_by_id(bot_id)
            if not bot or bot.model_status != "ready":
                continue

            timeframes = bot.timeframes.split(",")
            for tf in timeframes:
                if not has_model(bot.symbol, tf):
                    continue
                try:
                    fine_tune(bot.symbol, tf, epochs=3, batch_size=64)
                except Exception as e:
                    logger.error(
                        f"Failed to fine-tune {bot.symbol}/{tf} for bot {bot_id}: {e}",
                        exc_info=True,
                    )

        logger.info(f"LSTM model update completed for {len(bot_ids)} bot(s)")
    except Exception as e:
        logger.error(f"Error in update_lstm_models: {e}", exc_info=True)
    finally:
        db.close()


@celery.task(name="app.workers.lstm_tasks.restart_active_lstm_bots")
def restart_active_lstm_bots():
    """Restart LSTM bot tasks for all active bots."""
    db: Session = SessionLocal()
    try:
        bot_repo = LstmBotRepository(db)
        bot_ids = bot_repo.list_active_ids()
        for bot_id in bot_ids:
            run_lstm_bot.delay(bot_id)
            logger.info(f"Restarted LSTM bot task for bot_id={bot_id}")
        logger.info(f"Restarted {len(bot_ids)} active LSTM bot(s)")
    except Exception as e:
        logger.error(f"Error restarting LSTM bots: {e}", exc_info=True)
    finally:
        db.close()
