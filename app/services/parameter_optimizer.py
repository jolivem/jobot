"""Grid-search parameter optimizer for trading bots."""

import logging
from dataclasses import dataclass
from app.services.backtest_engine import run_backtest, BacktestResult

logger = logging.getLogger(__name__)

DEFAULT_GRID_LEVELS = [10]
DEFAULT_SELL_PERCENTAGES = [2.5, 3.0, 4.0]
SCREENING_GRID_LEVELS = [10]
SCREENING_SELL_PERCENTAGES = [2.5, 3.0, 4.0]


@dataclass
class OptimizationResult:
    """Best parameter set found by optimization."""

    best_params: BacktestResult
    all_results: list[BacktestResult]
    data_size: int


def generate_parameter_grid(
    close_prices: list[float],
    grid_levels_options: list[int] | None = None,
    sell_percentage_options: list[float] | None = None,
) -> list[dict]:
    """Generate parameter combinations using P0-P90 price range.

    Uses P0 (min) and P90 as the fixed price range,
    then varies grid_levels and sell_percentage.
    """
    if grid_levels_options is None:
        grid_levels_options = DEFAULT_GRID_LEVELS
    if sell_percentage_options is None:
        sell_percentage_options = DEFAULT_SELL_PERCENTAGES

    prices_sorted = sorted(close_prices)
    n = len(prices_sorted)

    def percentile(p: float) -> float:
        idx = int(n * p / 100)
        return prices_sorted[min(idx, n - 1)]

    min_price = round(percentile(0), 8)
    max_price = round(percentile(90), 8)

    if max_price <= min_price * 1.02:
        return []

    combos = []
    for gl in grid_levels_options:
        for sp in sell_percentage_options:
            combos.append({
                "min_price": min_price,
                "max_price": max_price,
                "grid_levels": gl,
                "sell_percentage": sp,
            })

    return combos


def optimize_parameters(
    symbol: str,
    close_prices: list[float],
    total_amount: float = 1000.0,
    grid_levels_options: list[int] | None = None,
    sell_percentage_options: list[float] | None = None,
    top_n: int = 10,
) -> OptimizationResult:
    """Run grid-search optimization on the full dataset.

    1. Generate parameter grid from price percentiles (P0-P90).
    2. Run backtest on each combination using all data.
    3. Pick the best by total_pnl_pct.

    Args:
        symbol: Trading pair symbol.
        close_prices: Chronological list of prices.
        total_amount: Budget for simulation.
        grid_levels_options: Grid levels to test.
        sell_percentage_options: Sell percentages to test.
        top_n: Number of top results to return.

    Returns:
        OptimizationResult with best params.
    """
    combos = generate_parameter_grid(
        close_prices,
        grid_levels_options=grid_levels_options,
        sell_percentage_options=sell_percentage_options,
    )

    logger.info(f"Optimizing {symbol}: {len(combos)} combinations on {len(close_prices)} prices")

    results: list[BacktestResult] = []
    for params in combos:
        result = run_backtest(
            symbol=symbol,
            close_prices=close_prices,
            total_amount=total_amount,
            **params,
        )
        results.append(result)

    # Sort by total_pnl_pct descending
    results.sort(key=lambda r: r.total_pnl_pct, reverse=True)

    if not results:
        raise ValueError(f"No valid parameter combinations for {symbol}")

    best = results[0]

    return OptimizationResult(
        best_params=best,
        all_results=results[:top_n],
        data_size=len(close_prices),
    )
