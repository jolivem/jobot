"""Fixed-price grid trading strategy.

Implements a grid buy/sell strategy with evenly-spaced price levels:
- buy_levels[0]=max_price .. buy_levels[grid_levels]=min_price
- Each level has a status: pending, bought, sold
- First buy when min_price <= price <= max_price (immediate, no pullback needed)
- Subsequent buys at levels where price <= level.price, with pullback confirmation
- Sells each position when price rises by sell_percentage from entry + pullback confirmation
- Restarts a new cycle when all positions are closed
"""

import logging
from app.models.trading_bot import TradingBot
from app.core.config import settings

logger = logging.getLogger(__name__)


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
        state: Runtime state from Redis:
            - positions: list of open positions
            - lowest_price: lowest price seen in current cycle
            - buy_levels: list of {"level_index", "price", "status"}
        previous_price: Price from the previous tick (None on first tick).

    Returns:
        A tuple of (decisions, updated_state).
        decisions: list of {"side": "buy"|"sell", "quantity": float, "entry_price": float, ...}
        updated_state: the new state to persist in Redis.
    """
    positions = state.get("positions", [])
    lowest_price = state.get("lowest_price")
    buy_levels = state.get("buy_levels", [])
    decisions = []

    buy_pullback_pct = settings.BUY_PULLBACK_PCT
    sell_pullback_pct = settings.SELL_PULLBACK_PCT
    fee_pct = settings.FEE_PCT

    # === No positions: first buy or restart after all sold ===
    if not positions:
        if bot.min_price <= current_price <= bot.max_price:
            qty = bot.total_amount / bot.grid_levels / current_price

            # Reset all levels to pending for new cycle.
            # Assign first buy to the highest grid level at or below current_price,
            # so the next buy targets a level with proper grid-step distance.
            for lvl in buy_levels:
                lvl["status"] = "pending"
            first_level_index = -1
            for lvl in buy_levels:
                if lvl["price"] <= current_price:
                    first_level_index = lvl["level_index"]
                    lvl["status"] = "bought"
                    break

            decisions.append({
                "side": "buy",
                "quantity": qty,
                "entry_price": current_price,
                "grid_level": first_level_index,
            })
            positions.append({
                "qty": qty,
                "entry": current_price,
                "highest": current_price,
                "fee": qty * current_price * fee_pct,
                "grid_level": first_level_index,
            })
            lowest_price = current_price
            logger.info(
                f"Bot {bot.id}: BUY @ {current_price:.8f} "
                f"(qty: {qty:.6f}, positions: {len(positions)}, "
                f"level: {first_level_index}/{len(buy_levels)})"
            )
        state["positions"] = positions
        state["lowest_price"] = lowest_price
        state["buy_levels"] = buy_levels
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
                    "_closed_position": dict(pos),
                })
                to_close.append(pos)
                logger.info(
                    f"Bot {bot.id}: SELL @ {current_price:.8f} "
                    f"(qty: {pos['qty']:.6f}, gain: {net_gain:.4f} USDC, "
                    f"positions: {len(positions) - len(to_close)})"
                )

    for pos in to_close:
        positions.remove(pos)
        # Mark level as sold (available for re-buy)
        gl = pos.get("grid_level")
        if gl is not None and gl >= 0:
            for lvl in buy_levels:
                if lvl["level_index"] == gl:
                    lvl["status"] = "sold"
                    break

    # If all positions closed, reset for next cycle
    if not positions:
        lowest_price = None
        for lvl in buy_levels:
            lvl["status"] = "pending"
        state["positions"] = positions
        state["lowest_price"] = lowest_price
        state["buy_levels"] = buy_levels
        return decisions, state

    # === Check buys: find the best level to buy (pending or sold) ===
    if previous_price is None or len(positions) >= bot.grid_levels:
        state["positions"] = positions
        state["lowest_price"] = lowest_price
        state["buy_levels"] = buy_levels
        return decisions, state

    occupied_levels = {pos.get("grid_level") for pos in positions}
    lowest_entry = min(p["entry"] for p in positions)

    if current_price <= bot.max_price and current_price < lowest_entry:
        # Find the deepest (highest-index) available level where price has dropped to.
        # Only consider levels below the lowest open position entry.
        # Reversed iteration: first match = level closest above current_price.
        target_lvl = None
        for lvl in reversed(buy_levels):
            if lvl["status"] not in ("pending", "sold"):
                continue
            if lvl["level_index"] in occupied_levels:
                continue
            if lvl["price"] >= lowest_entry:
                continue
            if current_price <= lvl["price"]:
                target_lvl = lvl
                break

        if target_lvl is not None:
            pullback_price = lowest_price * (1.0 + buy_pullback_pct)
            if current_price < previous_price and current_price >= pullback_price:
                qty = bot.total_amount / bot.grid_levels / current_price
                is_rebuy = target_lvl["status"] == "sold"
                target_lvl["status"] = "bought"
                decisions.append({
                    "side": "buy",
                    "quantity": qty,
                    "entry_price": current_price,
                    "grid_level": target_lvl["level_index"],
                })
                positions.append({
                    "qty": qty,
                    "entry": current_price,
                    "highest": current_price,
                    "fee": qty * current_price * fee_pct,
                    "grid_level": target_lvl["level_index"],
                })
                lowest_price = current_price
                label = "RE-BUY" if is_rebuy else "BUY"
                logger.info(
                    f"Bot {bot.id}: {label} @ {current_price:.8f} "
                    f"(qty: {qty:.6f}, positions: {len(positions)}, "
                    f"level: {target_lvl['level_index']}/{len(buy_levels)})"
                )

    state["positions"] = positions
    state["lowest_price"] = lowest_price
    state["buy_levels"] = buy_levels
    return decisions, state


def reconstruct_state_from_trades(bot: TradingBot, trades: list, buy_levels_db: list = None) -> dict:
    """Reconstruct bot state from DB trades and buy_levels.

    Args:
        bot: The trading bot configuration.
        trades: List of Trade objects (any order, will be sorted internally).
        buy_levels_db: List of BuyLevel objects from DB (optional).

    Returns:
        A reconstructed state dict suitable for decide_trade().
    """
    fee_pct = settings.FEE_PCT

    # Sort chronologically (oldest first)
    sorted_trades = sorted(trades, key=lambda t: t.created_at)

    # Replay trades: BUY pushes, SELL removes matching position
    open_positions = []
    for t in sorted_trades:
        if t.trade_type == "buy":
            open_positions.append({
                "qty": t.quantity,
                "entry": t.price,
                "highest": t.price,
                "fee": t.quantity * t.price * fee_pct,
                "grid_level": getattr(t, "grid_level", None),
            })
        elif t.trade_type == "sell" and open_positions:
            # Match by grid_level if available, otherwise FIFO
            sell_gl = getattr(t, "grid_level", None)
            matched = False
            if sell_gl is not None:
                for i, pos in enumerate(open_positions):
                    if pos["grid_level"] == sell_gl:
                        open_positions.pop(i)
                        matched = True
                        break
            if not matched:
                open_positions.pop(0)

    # Build buy_levels from DB if available
    if buy_levels_db:
        buy_levels = [
            {"level_index": bl.level_index, "price": bl.price, "status": bl.status}
            for bl in buy_levels_db
        ]
    else:
        # Create buy_levels from bot config (migration path)
        buy_levels = _create_buy_levels_from_config(bot)
        # Set statuses from open positions
        occupied_grid_levels = {p["grid_level"] for p in open_positions if p.get("grid_level") is not None and p["grid_level"] >= 0}
        # Replay all trades to find sold levels
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
        for lvl in buy_levels:
            idx = lvl["level_index"]
            if idx in occupied_grid_levels:
                lvl["status"] = "bought"
            elif idx in sold_levels:
                lvl["status"] = "sold"

    if not open_positions:
        return {
            "positions": [],
            "lowest_price": None,
            "buy_levels": buy_levels,
        }

    # Conservative lowest_price: minimum entry among open positions
    lowest_price = min(p["entry"] for p in open_positions)

    logger.info(
        f"Bot {bot.id}: Reconstructed state from {len(sorted_trades)} trades: "
        f"{len(open_positions)} open positions"
    )

    return {
        "positions": open_positions,
        "lowest_price": lowest_price,
        "buy_levels": buy_levels,
    }


def _create_buy_levels_from_config(bot: TradingBot) -> list[dict]:
    """Create buy_levels list from bot config (level 0=max .. grid_levels=min)."""
    step = (bot.max_price - bot.min_price) / bot.grid_levels if bot.grid_levels > 0 else 0
    return [
        {"level_index": i, "price": round(bot.max_price - i * step, 8), "status": "pending"}
        for i in range(bot.grid_levels + 1)
    ]
