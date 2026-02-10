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
            })
            positions.append({
                "qty": qty,
                "entry": current_price,
                "highest": current_price,
                "fee": qty * current_price * fee_pct,
            })
            # Grid levels are pre-computed between max_price and min_price
            grid_prices = compute_grid(bot.max_price, bot.min_price, bot.grid_levels)
            # Find first grid level below the buy price
            next_grid_index = len(grid_prices)
            for i, gp in enumerate(grid_prices):
                if gp < current_price:
                    next_grid_index = i
                    break
            lowest_price = None
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
    if (
        previous_price is not None
        and next_grid_index < len(grid_prices)
        and current_price <= bot.max_price
    ):
        target = grid_prices[next_grid_index]
        if current_price <= target:
            # Price has reached the grid level, check for pullback confirmation
            pullback_price = lowest_price * (1.0 + buy_pullback_pct)
            if current_price < previous_price and current_price >= pullback_price:
                qty = bot.total_amount / bot.grid_levels / current_price
                decisions.append({
                    "side": "buy",
                    "quantity": qty,
                    "entry_price": current_price,
                })
                positions.append({
                    "qty": qty,
                    "entry": current_price,
                    "highest": current_price,
                    "fee": qty * current_price * fee_pct,
                })
                next_grid_index += 1
                lowest_price = current_price
                logger.info(
                    f"Bot {bot.id}: BUY @ {current_price:.8f} "
                    f"(qty: {qty:.6f}, positions: {len(positions)}, "
                    f"grid level: {next_grid_index}/{len(grid_prices)})"
                )

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
    # Find first grid level below first buy price
    start_index = len(grid_prices)
    for i, gp in enumerate(grid_prices):
        if gp < first_buy_price:
            start_index = i
            break
    # next_grid_index = start_index + number of grid buys made
    next_grid_index = start_index + (len(open_positions) - 1)

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
