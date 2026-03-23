"""Shared P&L computation logic used by stats endpoint and snapshot task."""

from app.core.config import settings


def compute_bot_pnl(trades: list, current_price: float | None) -> dict:
    """Compute realized and unrealized P&L for a single bot's trades.

    Args:
        trades: List of Trade objects sorted chronologically (oldest first).
        current_price: Current market price (None if unavailable).

    Returns:
        Dict with realized_pnl, unrealized_pnl, total_pnl,
        open_positions_count, open_positions_cost, open_positions_qty,
        open_positions_value.
    """
    fee_pct = settings.FEE_PCT

    buys_by_id = {t.id: t for t in trades if t.trade_type == "buy"}
    buy_queue = [t for t in trades if t.trade_type == "buy"]
    matched_buy_ids: set = set()
    realized_pnl = 0.0

    for t in trades:
        if t.trade_type != "sell":
            continue

        buy = None
        if t.matched_buy_trade_id and t.matched_buy_trade_id in buys_by_id:
            candidate = buys_by_id[t.matched_buy_trade_id]
            if candidate.id not in matched_buy_ids:
                buy = candidate
        if buy is None:
            for b in buy_queue:
                if b.id not in matched_buy_ids:
                    buy = b
                    break
        if buy is None:
            continue

        matched_buy_ids.add(buy.id)
        buy_fee = buy.price * buy.quantity * fee_pct
        sell_fee = t.price * t.quantity * fee_pct
        profit = (t.price - buy.price) * t.quantity - buy_fee - sell_fee
        realized_pnl += profit

    open_buys = [t for t in trades if t.trade_type == "buy" and t.id not in matched_buy_ids]
    open_cost = sum(b.price * b.quantity for b in open_buys)
    open_qty = sum(b.quantity for b in open_buys)
    open_value = sum(b.quantity * current_price for b in open_buys) if current_price is not None else None
    unrealized_pnl = (open_value - open_cost) if open_value is not None else 0.0

    return {
        "realized_pnl": realized_pnl,
        "unrealized_pnl": unrealized_pnl,
        "total_pnl": realized_pnl + unrealized_pnl,
        "open_positions_count": len(open_buys),
        "open_positions_cost": open_cost,
        "open_positions_qty": open_qty,
        "open_positions_value": open_value,
    }
