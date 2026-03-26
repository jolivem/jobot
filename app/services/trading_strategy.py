"""Fixed-price grid trading strategy.

Implements a grid buy/sell strategy with evenly-spaced price levels:
- Grid levels are pre-computed between max_price and min_price
- First buy when min_price <= price <= max_price (immediate, no pullback needed)
- Subsequent buys at grid levels below first buy price, with pullback confirmation
- Sells each position when price rises by sell_percentage from entry + pullback confirmation
- Restarts a new cycle when all positions are closed and min_price <= price <= max_price
"""

import logging
from app.models.trading_bot import TradingBot
from app.core.config import settings

logger = logging.getLogger(__name__)


def compute_grid(max_price: float, min_price: float, grid_levels: int) -> list[float]:
    """Compute the grid price levels between max_price and min_price.

    Returns grid_levels-1 evenly-spaced levels between max_price and min_price.
    If max_price <= min_price or grid_levels <= 1, returns [].
    """
    if grid_levels <= 1 or max_price <= min_price:
        return []
    step = (max_price - min_price) / grid_levels
    return [max_price - i * step for i in range(1, grid_levels)]


def decide_trade(
    bot: TradingBot,
    current_price: float,
    state: dict,
    previous_price: float | None,
) -> tuple[list[dict], dict]:
    """Decide whether to buy, sell, or do nothing.

    Args:
        bot: The trading bot configuration.
        current_price: Current market price from Redis.
        state: Runtime state from Redis (positions, lowest_price, grid_prices, next_grid_index).
        previous_price: Price from the previous tick (None on first tick).

    Returns:
        A tuple of (decisions, updated_state).
        decisions: list of {"side": "buy"|"sell", "quantity": float, "entry_price": float}
        updated_state: the new state to persist in Redis.
    """
    positions = state.get("positions", [])
    lowest_price = state.get("lowest_price")
    grid_prices = state.get("grid_prices", [])
    next_grid_index = state.get("next_grid_index", 0)
    decisions = []

    buy_pullback_pct = settings.BUY_PULLBACK_PCT
    sell_pullback_pct = settings.SELL_PULLBACK_PCT
    fee_pct = settings.FEE_PCT

    # === No positions: first buy or restart after all sold ===
    if not positions:
        if bot.min_price <= current_price <= bot.max_price:
            qty = bot.total_amount / bot.grid_levels / current_price
            decisions.append({
                "side": "buy",
                "quantity": qty,
                "entry_price": current_price,
                "grid_level": -1,
            })
            positions.append({
                "qty": qty,
                "entry": current_price,
                "highest": current_price,
                "fee": qty * current_price * fee_pct,
                "grid_level": -1,  # initial buy, not a grid level
            })
            # Grid levels are pre-computed between max_price and min_price
            grid_prices = compute_grid(bot.max_price, bot.min_price, bot.grid_levels)
            step = (bot.max_price - bot.min_price) / bot.grid_levels if bot.grid_levels > 0 else 0
            # Find first grid level meaningfully below the buy price
            # (skip levels within 10% of a step to avoid immediate re-buy)
            min_target = current_price - step * 0.1
            next_grid_index = len(grid_prices)
            for i, gp in enumerate(grid_prices):
                if gp < min_target:
                    next_grid_index = i
                    break
            lowest_price = current_price
            logger.info(
                f"Bot {bot.id}: BUY @ {current_price:.8f} "
                f"(qty: {qty:.6f}, positions: {len(positions)}, "
                f"grid: {len(grid_prices)} levels)"
            )
        state["positions"] = positions
        state["lowest_price"] = lowest_price
        state["grid_prices"] = grid_prices
        state["next_grid_index"] = next_grid_index
        return decisions, state

    # === Update lowest_price tracking ===
    if lowest_price is None or current_price < lowest_price:
        lowest_price = current_price

    # === Update highest per position ===
    for pos in positions:
        if current_price > pos["highest"]:
            pos["highest"] = current_price

    # === Check sells ===
    to_close = []
    for pos in positions:
        gain_pct = current_price / pos["entry"] - 1.0
        if gain_pct >= bot.sell_percentage / 100.0:
            if current_price <= pos["highest"] * (1.0 - sell_pullback_pct):
                usdc_out = pos["qty"] * current_price
                fee = usdc_out * fee_pct
                net_gain = usdc_out - fee - (pos["entry"] * pos["qty"]) - pos["fee"]
                decisions.append({
                    "side": "sell",
                    "quantity": pos["qty"],
                    "entry_price": current_price,
                    "buy_entry": pos["entry"],
                })
                to_close.append(pos)
                logger.info(
                    f"Bot {bot.id}: SELL @ {current_price:.8f} "
                    f"(qty: {pos['qty']:.6f}, gain: {net_gain:.4f} USDC, "
                    f"positions: {len(positions) - len(to_close)})"
                )

    for pos in to_close:
        positions.remove(pos)

    # If all positions closed, reset for next cycle
    if not positions:
        lowest_price = None
        grid_prices = []
        next_grid_index = 0
        state["positions"] = positions
        state["lowest_price"] = lowest_price
        state["grid_prices"] = grid_prices
        state["next_grid_index"] = next_grid_index
        return decisions, state

    # === Check grid buy ===
    occupied_levels = {pos.get("grid_level") for pos in positions}
    if (
        previous_price is not None
        and next_grid_index < len(grid_prices)
        and len(positions) < bot.grid_levels
        and current_price <= bot.max_price
        and next_grid_index not in occupied_levels
    ):
        target = grid_prices[next_grid_index]
        if current_price <= target:
            # Price has reached the grid level, check for pullback confirmation
            pullback_price = lowest_price * (1.0 + buy_pullback_pct)
            if current_price < previous_price and current_price >= pullback_price:
                qty = bot.total_amount / bot.grid_levels / current_price
                grid_lvl = next_grid_index
                decisions.append({
                    "side": "buy",
                    "quantity": qty,
                    "entry_price": current_price,
                    "grid_level": grid_lvl,
                })
                positions.append({
                    "qty": qty,
                    "entry": current_price,
                    "highest": current_price,
                    "fee": qty * current_price * fee_pct,
                    "grid_level": grid_lvl,
                })
                next_grid_index += 1
                lowest_price = current_price
                logger.info(
                    f"Bot {bot.id}: BUY @ {current_price:.8f} "
                    f"(qty: {qty:.6f}, positions: {len(positions)}, "
                    f"grid level: {next_grid_index}/{len(grid_prices)})"
                )

    # === Re-buy at freed levels (sold positions above next_grid_index) ===
    if (
        previous_price is not None
        and len(positions) < bot.grid_levels
        and current_price <= bot.max_price
        and to_close  # only check after a sell just happened
    ):
        for freed_pos in to_close:
            freed_lvl = freed_pos.get("grid_level")
            if freed_lvl is None or freed_lvl < 0:
                continue
            if freed_lvl in occupied_levels:
                continue
            if freed_lvl < next_grid_index and current_price <= grid_prices[freed_lvl]:
                qty = bot.total_amount / bot.grid_levels / current_price
                decisions.append({
                    "side": "buy",
                    "quantity": qty,
                    "entry_price": current_price,
                    "grid_level": freed_lvl,
                })
                positions.append({
                    "qty": qty,
                    "entry": current_price,
                    "highest": current_price,
                    "fee": qty * current_price * fee_pct,
                    "grid_level": freed_lvl,
                })
                occupied_levels.add(freed_lvl)
                logger.info(
                    f"Bot {bot.id}: RE-BUY @ {current_price:.8f} "
                    f"(qty: {qty:.6f}, positions: {len(positions)}, "
                    f"freed grid level: {freed_lvl}/{len(grid_prices)})"
                )
                break  # one re-buy per tick

    state["positions"] = positions
    state["lowest_price"] = lowest_price
    state["grid_prices"] = grid_prices
    state["next_grid_index"] = next_grid_index
    return decisions, state


def reconstruct_state_from_trades(bot: TradingBot, trades: list) -> dict:
    """Reconstruct bot state from DB trades (for recovery after Redis data loss).

    Args:
        bot: The trading bot configuration.
        trades: List of Trade objects (any order, will be sorted internally).

    Returns:
        A reconstructed state dict suitable for decide_trade().
    """
    fee_pct = settings.FEE_PCT

    # Sort chronologically (oldest first)
    sorted_trades = sorted(trades, key=lambda t: t.created_at)

    # Replay trades: BUY pushes, SELL pops (FIFO)
    open_positions = []
    for t in sorted_trades:
        if t.trade_type == "buy":
            open_positions.append({
                "qty": t.quantity,
                "entry": t.price,
                "highest": t.price,  # conservative: will catch up on next ticks
                "fee": t.quantity * t.price * fee_pct,
                "grid_level": getattr(t, "grid_level", None),
            })
        elif t.trade_type == "sell" and open_positions:
            open_positions.pop(0)

    if not open_positions:
        return {
            "positions": [],
            "lowest_price": None,
            "grid_prices": [],
            "next_grid_index": 0,
        }

    # Grid is always computed from max_price and min_price
    first_buy_price = open_positions[0]["entry"]
    grid_prices = compute_grid(bot.max_price, bot.min_price, bot.grid_levels)
    step = (bot.max_price - bot.min_price) / bot.grid_levels if bot.grid_levels > 0 else 0
    # Find first grid level below first buy price (with 10% step margin)
    min_target = first_buy_price - step * 0.1
    start_index = len(grid_prices)
    for i, gp in enumerate(grid_prices):
        if gp < min_target:
            start_index = i
            break
    # next_grid_index = start_index + number of grid buys made
    next_grid_index = start_index + (len(open_positions) - 1)

    # Assign grid_level to positions that don't have one (legacy trades without grid_level in DB)
    if open_positions[0]["grid_level"] is None:
        open_positions[0]["grid_level"] = -1
    for j in range(1, len(open_positions)):
        if open_positions[j]["grid_level"] is None:
            open_positions[j]["grid_level"] = start_index + (j - 1)

    # Conservative lowest_price: minimum entry among open positions
    lowest_price = min(p["entry"] for p in open_positions)

    logger.info(
        f"Bot {bot.id}: Reconstructed state from {len(sorted_trades)} trades: "
        f"{len(open_positions)} open positions, grid level {next_grid_index}/{len(grid_prices)}"
    )

    return {
        "positions": open_positions,
        "lowest_price": lowest_price,
        "grid_prices": grid_prices,
        "next_grid_index": next_grid_index,
    }
