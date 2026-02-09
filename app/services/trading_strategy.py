"""Grid trading strategy.

Implements a grid buy/sell strategy:
- Buys when price drops by buy_percentage from lowest entry, confirmed by a pullback
- Sells each position when price rises by sell_percentage from entry, confirmed by a pullback
- Restarts a new cycle when all positions are closed and price <= max_price
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
        state: Runtime state from Redis (positions, lowest_price).
        previous_price: Price from the previous tick (None on first tick).

    Returns:
        A tuple of (decisions, updated_state).
        decisions: list of {"side": "buy"|"sell", "quantity": float, "entry_price": float}
        updated_state: the new state to persist in Redis.
    """
    positions = state.get("positions", [])
    lowest_price = state.get("lowest_price")
    decisions = []

    buy_pullback_pct = settings.BUY_PULLBACK_PCT
    sell_pullback_pct = settings.SELL_PULLBACK_PCT
    fee_pct = settings.FEE_PCT

    # === No positions: first buy or restart after all sold ===
    if not positions:
        if current_price <= bot.max_price:
            qty = bot.total_amount / current_price
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
            lowest_price = None
            logger.info(
                f"Bot {bot.id}: BUY @ {current_price:.8f} "
                f"(qty: {qty:.6f}, positions: {len(positions)})"
            )
        state["positions"] = positions
        state["lowest_price"] = lowest_price
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
    profit = 0.0
    for pos in positions:
        gain_pct = current_price / pos["entry"] - 1.0
        if gain_pct >= bot.sell_percentage / 100.0:
            if current_price <= pos["highest"] * (1.0 - sell_pullback_pct):
                usdc_out = pos["qty"] * current_price
                fee = usdc_out * fee_pct
                net_gain = usdc_out - fee - (pos["entry"] * pos["qty"]) - pos["fee"]
                profit += net_gain
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
        state["positions"] = positions
        state["lowest_price"] = lowest_price
        return decisions, state

    # === Check buy (grid level) ===
    if previous_price is not None and current_price <= bot.max_price:
        lowest_entry = min(p["entry"] for p in positions)
        drop_from_lowest_entry = 1.0 - current_price / lowest_entry

        if drop_from_lowest_entry >= bot.buy_percentage / 100.0:
            pullback_price = lowest_price * (1.0 + buy_pullback_pct)
            if current_price < previous_price and current_price >= pullback_price:
                qty = bot.total_amount / current_price
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
                # Reset lowest_price to current price so the next buy requires
                # a fresh drop of buy_percentage from this new entry
                lowest_price = current_price
                logger.info(
                    f"Bot {bot.id}: BUY @ {current_price:.8f} "
                    f"(qty: {qty:.6f}, positions: {len(positions)})"
                )

    state["positions"] = positions
    state["lowest_price"] = lowest_price
    return decisions, state
