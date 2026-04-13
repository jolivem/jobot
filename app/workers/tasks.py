import time
from sqlalchemy.orm import Session
from app.workers.celery_app import celery
from app.core.db import SessionLocal
from app.repositories.trading_bot_repo import TradingBotRepository
from app.repositories.trade_repo import TradeRepository
from app.repositories.buy_level_repo import BuyLevelRepository
from app.services.binance_price_service import BinancePriceService
from app.services.binance_trade_service import BinanceTradeService
from app.services.trading_strategy import decide_trade, reconstruct_state_from_trades, _create_buy_levels_from_config
from app.core.cache import RedisCache
from app.core.config import settings
from app.core.encryption import decrypt
import logging

logger = logging.getLogger(__name__)


@celery.task(name="app.workers.tasks.snapshot_pnl")
def snapshot_pnl():
    """Snapshot total P&L for each bot, once per hour."""
    from datetime import datetime, timezone
    from app.repositories.pnl_snapshot_repo import PnlSnapshotRepository
    from app.services.pnl_service import compute_bot_pnl

    db: Session = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        snapshot_at = now.replace(minute=0, second=0, microsecond=0)

        bot_repo = TradingBotRepository(db)
        trade_repo = TradeRepository(db)
        snap_repo = PnlSnapshotRepository(db)

        try:
            cache = RedisCache()
        except Exception:
            cache = None

        all_bots = bot_repo.list_all()
        for bot in all_bots:
            if snap_repo.exists(bot.id, snapshot_at):
                continue

            trades = trade_repo.list_by_bot(bot.id)
            trades.sort(key=lambda t: t.created_at)

            current_price = None
            if cache:
                try:
                    current_price = cache.get_price(bot.symbol)
                except Exception:
                    pass

            pnl = compute_bot_pnl(trades, current_price)

            snap_repo.create(
                user_id=bot.user_id,
                trading_bot_id=bot.id,
                realized_pnl=round(pnl["realized_pnl"], 6),
                unrealized_pnl=round(pnl["unrealized_pnl"], 6),
                total_pnl=round(pnl["total_pnl"], 6),
                snapshot_at=snapshot_at,
            )

        logger.info(f"P&L snapshot completed for {len(all_bots)} bots at {snapshot_at}")
    except Exception as e:
        logger.error(f"Error in snapshot_pnl: {e}", exc_info=True)
    finally:
        db.close()


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


def _load_or_create_buy_levels(db: Session, bot: "TradingBot", trades: list) -> list:
    """Load buy_levels from DB, or create them if missing (migration path)."""
    bl_repo = BuyLevelRepository(db)
    buy_levels_db = bl_repo.list_by_bot(bot.id)

    if not buy_levels_db:
        # First time: create levels in DB
        buy_levels_db = bl_repo.create_grid(bot.id, bot.max_price, bot.min_price, bot.grid_levels)
        logger.info(f"Bot {bot.id}: created {len(buy_levels_db)} buy_levels in DB")

        # Set statuses from existing trades
        if trades:
            sorted_trades = sorted(trades, key=lambda t: t.created_at)
            bought_levels = set()
            sold_levels = set()
            for t in sorted_trades:
                gl = getattr(t, "grid_level", None)
                if gl is None or gl < 0:
                    continue
                if t.trade_type == "buy":
                    bought_levels.add(gl)
                    sold_levels.discard(gl)
                elif t.trade_type == "sell":
                    if gl in bought_levels:
                        sold_levels.add(gl)
                        bought_levels.discard(gl)
            for gl in bought_levels:
                bl_repo.update_status(bot.id, gl, "bought")
            for gl in sold_levels:
                bl_repo.update_status(bot.id, gl, "sold")
            # Reload after updates
            buy_levels_db = bl_repo.list_by_bot(bot.id)

    return buy_levels_db


def _sync_buy_levels_to_db(db: Session, bot_id: int, buy_levels_state: list):
    """Sync buy_levels from Redis state to DB (only on changes)."""
    bl_repo = BuyLevelRepository(db)
    for lvl in buy_levels_state:
        bl_repo.update_status(bot_id, lvl["level_index"], lvl["status"])


def _init_bot_state(cache: RedisCache, bot_id: int) -> dict:
    """Load bot state from Redis, or reconstruct from DB trades + buy_levels."""
    state = cache.get_bot_state(bot_id)
    if state is not None:
        return state

    db: Session = SessionLocal()
    try:
        bot_repo = TradingBotRepository(db)
        bot = bot_repo.get_active_by_id(bot_id)
        if bot:
            trades = TradeRepository(db).list_by_bot(bot_id)
            buy_levels_db = _load_or_create_buy_levels(db, bot, trades)
            state = reconstruct_state_from_trades(bot, trades, buy_levels_db)
            cache.set_bot_state(bot_id, state)
            return state
    except Exception as e:
        logger.error(f"Bot {bot_id}: error reconstructing state: {e}", exc_info=True)
    finally:
        db.close()

    return {"positions": [], "lowest_price": None, "buy_levels": []}


def _resolve_binance_service(bot_id: int) -> BinanceTradeService | None:
    """Resolve Binance trade service for live trading."""
    if not settings.BINANCE_LIVE_TRADING:
        return None

    db: Session = SessionLocal()
    try:
        user = TradingBotRepository(db).get_user_for_bot(bot_id)
        if user and user.binance_api_key and user.binance_api_secret:
            api_key = decrypt(user.binance_api_key)
            api_secret = decrypt(user.binance_api_secret)
            logger.info(f"Bot {bot_id}: live trading enabled")
            return BinanceTradeService(api_key, api_secret)
        else:
            logger.warning(f"Bot {bot_id}: BINANCE_LIVE_TRADING=true but user has no API credentials, running in simulation")
    finally:
        db.close()
    return None


def _process_bot_tick(
    bot_id: int,
    cache: RedisCache,
    bot_states: dict,
    previous_prices: dict,
    binance_services: dict,
):
    """Process a single tick for one bot. Returns True if bot is still active."""
    db: Session = SessionLocal()
    try:
        bot_repo = TradingBotRepository(db)
        bot = bot_repo.get_active_by_id(bot_id)
        if not bot:
            logger.info(f"Bot {bot_id} is no longer active, removing from loop")
            cache.delete_bot_state(bot_id)
            return False

        # Read price from Redis
        price = cache.get_price(bot.symbol)
        if price is None:
            return True  # No price yet, skip this tick

        state = bot_states.get(bot_id, {"positions": [], "lowest_price": None, "buy_levels": []})
        previous_price = previous_prices.get(bot_id)
        binance_service = binance_services.get(bot_id)

        # Save buy_levels state before decisions (for rollback if orders fail)
        pre_decision_levels = [dict(lvl) for lvl in state.get("buy_levels", [])]

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
                        # Rollback state: restore position that wasn't actually sold
                        if decision["side"] == "sell" and "_closed_position" in decision:
                            state.setdefault("positions", []).append(decision["_closed_position"])
                            state["buy_levels"] = pre_decision_levels
                        # Rollback state: remove position that wasn't actually bought
                        elif decision["side"] == "buy":
                            positions = state.get("positions", [])
                            for i in range(len(positions) - 1, -1, -1):
                                if abs(positions[i]["entry"] - decision["entry_price"]) < 1e-8:
                                    positions.pop(i)
                                    break
                            state["buy_levels"] = pre_decision_levels
                        continue  # Skip recording if real order failed

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
                    grid_level=decision.get("grid_level"),
                )

                # Sync state positions with actual Binance fill
                if binance_service and decision["side"] == "buy":
                    for pos in reversed(state.get("positions", [])):
                        if abs(pos["entry"] - decision["entry_price"]) < 1e-8:
                            pos["qty"] = filled_qty
                            pos["entry"] = filled_price
                            pos["fee"] = filled_qty * filled_price * settings.FEE_PCT
                            break

            # Sync buy_levels to DB after trades
            _sync_buy_levels_to_db(db, bot_id, state.get("buy_levels", []))

        # Persist updated state to Redis
        bot_states[bot_id] = state
        cache.set_bot_state(bot_id, state)
        previous_prices[bot_id] = price

    except Exception as e:
        logger.error(f"Bot {bot_id}: unexpected error: {e}", exc_info=True)
    finally:
        db.close()

    return True


@celery.task(name="app.workers.tasks.run_all_bots", bind=True)
def run_all_bots(self):
    """Single long-running task that manages all active trading bots.

    Loops every BOT_POLL_INTERVAL seconds, iterates over all active bots,
    and runs the grid trading strategy for each. This replaces the previous
    one-task-per-bot architecture to reduce memory usage on constrained
    hardware (e.g., Raspberry Pi).
    """
    logger.info("Starting unified trading bot loop")
    cache = RedisCache()

    # Acquire global lock to prevent duplicate loops
    LOCK_KEY = "bot_loop_lock"
    LOCK_TTL = settings.BOT_POLL_INTERVAL * 5
    if not cache.client.set(LOCK_KEY, "1", nx=True, ex=LOCK_TTL):
        logger.warning("run_all_bots: another instance is already running, aborting")
        return

    bot_states: dict[int, dict] = {}
    previous_prices: dict[int, float] = {}
    binance_services: dict[int, BinanceTradeService | None] = {}
    db_refresh_interval = 10  # refresh active bot list every N ticks
    iteration = 0
    active_bot_ids: list[int] = []
    tick_times: list[int] = []  # last 20 tick durations in ms

    try:
        while True:
            # Renew global lock
            cache.client.expire(LOCK_KEY, LOCK_TTL)
            # Periodically refresh the list of active bots from DB
            if iteration % db_refresh_interval == 0:
                db: Session = SessionLocal()
                try:
                    new_ids = TradingBotRepository(db).list_active_ids()
                except Exception as e:
                    logger.error(f"Error fetching active bots: {e}", exc_info=True)
                    new_ids = active_bot_ids  # keep previous list on error
                finally:
                    db.close()

                # Initialize state for newly added bots
                for bot_id in new_ids:
                    if bot_id not in bot_states:
                        bot_states[bot_id] = _init_bot_state(cache, bot_id)
                        binance_services[bot_id] = _resolve_binance_service(bot_id)
                        logger.info(f"Bot {bot_id}: added to trading loop")

                # Clean up removed/deactivated bots
                for bot_id in list(bot_states.keys()):
                    if bot_id not in new_ids:
                        bot_states.pop(bot_id, None)
                        previous_prices.pop(bot_id, None)
                        binance_services.pop(bot_id, None)
                        logger.info(f"Bot {bot_id}: removed from trading loop")

                active_bot_ids = new_ids

            # Process each active bot
            tick_start = time.monotonic()
            for bot_id in active_bot_ids:
                still_active = _process_bot_tick(
                    bot_id, cache, bot_states, previous_prices, binance_services,
                )
                if not still_active:
                    bot_states.pop(bot_id, None)
                    previous_prices.pop(bot_id, None)
                    binance_services.pop(bot_id, None)

            tick_ms = int((time.monotonic() - tick_start) * 1000)
            tick_times.append(tick_ms)
            if len(tick_times) > 20:
                tick_times.pop(0)
            avg_ms = sum(tick_times) // len(tick_times)
            cache.client.setex("bot_loop_tick_ms", 30, str(avg_ms))

            iteration += 1
            time.sleep(settings.BOT_POLL_INTERVAL)
    except Exception as e:
        logger.error(f"Trading loop crashed: {e}", exc_info=True)
        raise
    finally:
        cache.client.delete(LOCK_KEY)
        logger.info("Trading loop stopped, released global lock")


# Keep old task name as alias so pending Celery messages don't fail
@celery.task(name="app.workers.tasks.run_trading_bot", bind=True)
def run_trading_bot(self, bot_id: int):
    """Deprecated: individual bot task. Now a no-op — bots are managed by run_all_bots."""
    logger.info(f"run_trading_bot({bot_id}) called but is now a no-op (managed by run_all_bots)")


@celery.task(name="app.workers.tasks.restart_active_bots")
def restart_active_bots():
    """Start the unified trading loop if not already running."""
    run_all_bots.delay()
    logger.info("Launched unified trading bot loop")
