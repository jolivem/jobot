"""Backtest engine: replays historical prices through decide_trade()."""

import math
from types import SimpleNamespace
from dataclasses import dataclass
from app.services.trading_strategy import decide_trade
from app.core.config import settings


@dataclass
class BacktestResult:
    """Metrics from a single backtest run."""

    total_pnl: float
    total_pnl_pct: float
    num_trades: int
    num_buys: int
    num_sells: int
    win_rate: float
    max_drawdown: float
    sharpe_ratio: float
    final_open_positions: int
    unrealized_pnl: float

    # Parameters used
    min_price: float
    max_price: float
    grid_levels: int
    sell_percentage: float
    total_amount: float


def run_backtest(
    symbol: str,
    close_prices: list[float],
    min_price: float,
    max_price: float,
    total_amount: float,
    sell_percentage: float,
    grid_levels: int,
) -> BacktestResult:
    """Run a single backtest simulation.

    Replays close_prices through decide_trade() and computes performance
    metrics. Uses the same trading logic as live bots.

    Args:
        symbol: Trading pair symbol.
        close_prices: Chronological list of close prices (oldest first).
        min_price..grid_levels: Bot parameters to simulate.

    Returns:
        BacktestResult with all performance metrics.
    """
    bot = SimpleNamespace(
        id=0,
        symbol=symbol,
        min_price=min_price,
        max_price=max_price,
        total_amount=total_amount,
        sell_percentage=sell_percentage,
        grid_levels=grid_levels,
    )
    fee_pct = settings.FEE_PCT

    state: dict = {
        "positions": [],
        "lowest_price": None,
        "grid_prices": [],
        "next_grid_index": 0,
    }

    previous_price: float | None = None
    open_buys: list[tuple[float, float]] = []  # (entry_price, quantity)
    realized_pnl = 0.0
    winning_sells = 0
    num_buys = 0
    num_sells = 0

    # Equity tracking for drawdown and Sharpe
    equity_curve: list[float] = []
    peak_equity = total_amount
    max_drawdown = 0.0

    for price in close_prices:
        decisions, state = decide_trade(bot, price, state, previous_price)

        for d in decisions:
            if d["side"] == "buy":
                num_buys += 1
                open_buys.append((d["entry_price"], d["quantity"]))
            elif d["side"] == "sell":
                num_sells += 1
                sell_value = d["entry_price"] * d["quantity"]
                sell_fee = sell_value * fee_pct
                if open_buys:
                    buy_price, buy_qty = open_buys.pop(0)
                    buy_cost = buy_price * buy_qty
                    buy_fee = buy_cost * fee_pct
                    trade_pnl = sell_value - sell_fee - buy_cost - buy_fee
                    realized_pnl += trade_pnl
                    if trade_pnl > 0:
                        winning_sells += 1

        # Compute equity: remaining cash + value of open positions
        invested = sum(bp * bq + bp * bq * fee_pct for bp, bq in open_buys)
        open_value = sum(bq * price for _, bq in open_buys)
        unrealized = open_value - invested
        equity = total_amount + realized_pnl + unrealized

        equity_curve.append(equity)
        if equity > peak_equity:
            peak_equity = equity
        if peak_equity > 0:
            drawdown = (peak_equity - equity) / peak_equity
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        previous_price = price

    # Unrealized P&L from remaining open positions
    last_price = close_prices[-1] if close_prices else 0.0
    unrealized_pnl = 0.0
    for bp, bq in open_buys:
        current_value = bq * last_price
        cost = bp * bq + bp * bq * fee_pct
        unrealized_pnl += current_value - cost

    total_pnl = realized_pnl + unrealized_pnl
    win_rate = winning_sells / num_sells if num_sells > 0 else 0.0

    # Simplified Sharpe ratio
    sharpe = 0.0
    if len(equity_curve) > 1:
        returns = []
        for i in range(1, len(equity_curve)):
            prev_eq = equity_curve[i - 1]
            if prev_eq != 0:
                returns.append((equity_curve[i] - prev_eq) / prev_eq)
        if returns:
            mean_r = sum(returns) / len(returns)
            var_r = sum((r - mean_r) ** 2 for r in returns) / len(returns)
            std_r = math.sqrt(var_r) if var_r > 0 else 1e-10
            sharpe = mean_r / std_r * math.sqrt(len(returns))

    return BacktestResult(
        total_pnl=round(total_pnl, 6),
        total_pnl_pct=round(total_pnl / total_amount * 100, 4) if total_amount > 0 else 0.0,
        num_trades=num_buys + num_sells,
        num_buys=num_buys,
        num_sells=num_sells,
        win_rate=round(win_rate, 4),
        max_drawdown=round(max_drawdown, 6),
        sharpe_ratio=round(sharpe, 4),
        final_open_positions=len(open_buys),
        unrealized_pnl=round(unrealized_pnl, 6),
        min_price=min_price,
        max_price=max_price,
        grid_levels=grid_levels,
        sell_percentage=sell_percentage,
        total_amount=total_amount,
    )
