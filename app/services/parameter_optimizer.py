"""Grid-search parameter optimizer for trading bots."""

import logging
from dataclasses import dataclass
from app.services.backtest_engine import run_backtest, BacktestResult

logger = logging.getLogger(__name__)

DEFAULT_GRID_LEVELS = [3, 5, 7, 10, 15, 20]
DEFAULT_SELL_PERCENTAGES = [0.5, 1.0, 1.5, 2.0, 3.0, 5.0]
SCREENING_GRID_LEVELS = [5, 10, 15]
SCREENING_SELL_PERCENTAGES = [1.0, 2.0, 3.0, 5.0]


@dataclass
class OptimizationResult:
    """Best parameter set with train and test metrics."""

    best_params: BacktestResult
    test_result: BacktestResult
    all_results: list[BacktestResult]
    train_size: int
    test_size: int


def generate_parameter_grid(
    close_prices: list[float],
    grid_levels_options: list[int] | None = None,
    sell_percentage_options: list[float] | None = None,
) -> list[dict]:
    """Generate smart parameter combinations based on price distribution.

    Price ranges are derived from percentiles of the historical data
    to avoid testing unrealistic min/max values.
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

    min_candidates = sorted(set([
        percentile(5), percentile(10), percentile(15), percentile(25),
    ]))
    max_candidates = sorted(set([
        percentile(75), percentile(85), percentile(90), percentile(95),
    ]))

    combos = []
    for min_p in min_candidates:
        for max_p in max_candidates:
            if max_p <= min_p * 1.02:
                continue
            for gl in grid_levels_options:
                for sp in sell_percentage_options:
                    combos.append({
                        "min_price": round(min_p, 8),
                        "max_price": round(max_p, 8),
                        "grid_levels": gl,
                        "sell_percentage": sp,
                    })

    return combos


def optimize_parameters(
    symbol: str,
    close_prices: list[float],
    total_amount: float = 1000.0,
    train_ratio: float = 0.7,
    grid_levels_options: list[int] | None = None,
    sell_percentage_options: list[float] | None = None,
    top_n: int = 10,
) -> OptimizationResult:
    """Run grid-search optimization with train/test split.

    1. Split close_prices into train (70%) / test (30%).
    2. Generate parameter grid from train data percentiles.
    3. Run backtest on each combination using train data.
    4. Pick the best by total_pnl_pct.
    5. Validate the best on test data.

    Args:
        symbol: Trading pair symbol.
        close_prices: Chronological list of prices.
        total_amount: Budget for simulation.
        train_ratio: Fraction of data for training (0.5-0.9).
        grid_levels_options: Grid levels to test.
        sell_percentage_options: Sell percentages to test.
        top_n: Number of top results to return.

    Returns:
        OptimizationResult with best params and validation.
    """
    split_idx = int(len(close_prices) * train_ratio)
    train_prices = close_prices[:split_idx]
    test_prices = close_prices[split_idx:]

    combos = generate_parameter_grid(
        train_prices,
        grid_levels_options=grid_levels_options,
        sell_percentage_options=sell_percentage_options,
    )

    logger.info(f"Optimizing {symbol}: {len(combos)} combinations on {len(train_prices)} train prices")

    results: list[BacktestResult] = []
    for params in combos:
        result = run_backtest(
            symbol=symbol,
            close_prices=train_prices,
            total_amount=total_amount,
            **params,
        )
        results.append(result)

    # Sort by total_pnl_pct descending
    results.sort(key=lambda r: r.total_pnl_pct, reverse=True)

    if not results:
        raise ValueError(f"No valid parameter combinations for {symbol}")

    best = results[0]

    # Validate best params on test data
    test_result = run_backtest(
        symbol=symbol,
        close_prices=test_prices,
        total_amount=total_amount,
        min_price=best.min_price,
        max_price=best.max_price,
        grid_levels=best.grid_levels,
        sell_percentage=best.sell_percentage,
    )

    return OptimizationResult(
        best_params=best,
        test_result=test_result,
        all_results=results[:top_n],
        train_size=len(train_prices),
        test_size=len(test_prices),
    )
