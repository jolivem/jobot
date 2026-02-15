#!/usr/bin/env python3
"""Standalone CLI screening script.

Scans all Binance USDC pairs, runs grid parameter optimization on each,
and outputs the results ranked by P&L%. No frontend, Redis, or DB needed.

Usage:
    python scripts/run_screening.py
    python scripts/run_screening.py --interval 1m --limit 10080 --top 30
    python scripts/run_screening.py --symbol BTCUSDC          # single symbol
    python scripts/run_screening.py --csv results.csv         # export to CSV

    # Use Binance Vision historical data (supports 1s candles):
    python scripts/run_screening.py --source vision --interval 1s --days 7
    python scripts/run_screening.py --source vision --interval 1m --days 7 --symbol SOLUSDC
"""

import os
import sys
import time
import argparse
import csv

# Set minimal env vars before importing app modules (DB/Redis not needed)
os.environ.setdefault("APP_ENV", "cli")
os.environ.setdefault("JWT_SECRET", "cli-not-used")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "3306")
os.environ.setdefault("DB_USER", "x")
os.environ.setdefault("DB_PASSWORD", "x")
os.environ.setdefault("DB_NAME", "x")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.klines_fetcher import fetch_klines, fetch_klines_vision
from app.services.parameter_optimizer import (
    optimize_parameters,
    SCREENING_GRID_LEVELS,
    SCREENING_SELL_PERCENTAGES,
)
from app.services.binance_price_service import BinancePriceService


def get_usdc_symbols() -> list[str]:
    """Fetch all USDC trading pairs from Binance."""
    return BinancePriceService().get_usdc_symbols()


def run_screening(
    symbols: list[str],
    interval: str,
    limit: int,
    total_amount: float,
    delay: float,
    source: str = "api",
    days: int = 7,
) -> list[dict]:
    """Run optimization on each symbol and return results."""
    results = []
    total = len(symbols)

    for i, symbol in enumerate(symbols, 1):
        progress = f"[{i}/{total}]"
        try:
            if source == "vision":
                klines = fetch_klines_vision(
                    symbol=symbol, interval=interval, days=days,
                )
            else:
                klines = fetch_klines(symbol=symbol, interval=interval, limit=limit)

            if len(klines) < 200:
                print(f"  {progress} {symbol:<15} skipped ({len(klines)} candles)")
                time.sleep(delay)
                continue

            close_prices = [k["close"] for k in klines]

            t0 = time.time()
            opt = optimize_parameters(
                symbol=symbol,
                close_prices=close_prices,
                total_amount=total_amount,
                grid_levels_options=SCREENING_GRID_LEVELS,
                sell_percentage_options=SCREENING_SELL_PERCENTAGES,
            )
            elapsed = time.time() - t0

            r = {
                "symbol": symbol,
                "train_pnl_pct": opt.best_params.total_pnl_pct,
                "test_pnl_pct": opt.test_result.total_pnl_pct,
                "trades": opt.best_params.num_trades,
                "win_rate": opt.best_params.win_rate,
                "max_drawdown": opt.best_params.max_drawdown,
                "sharpe": opt.best_params.sharpe_ratio,
                "min_price": opt.best_params.min_price,
                "max_price": opt.best_params.max_price,
                "grid_levels": opt.best_params.grid_levels,
                "sell_pct": opt.best_params.sell_percentage,
            }
            results.append(r)

            color = "\033[32m" if r["test_pnl_pct"] > 0 else "\033[31m"
            reset = "\033[0m"
            candle_info = f"{len(klines):>7} candles  " if source == "vision" else ""
            print(
                f"  {progress} {symbol:<15} {candle_info}"
                f"train: {r['train_pnl_pct']:+7.2f}%  "
                f"test: {color}{r['test_pnl_pct']:+7.2f}%{reset}  "
                f"trades: {r['trades']:>4}  "
                f"win: {r['win_rate']*100:5.1f}%  "
                f"({elapsed:.1f}s)"
            )

        except Exception as e:
            print(f"  {progress} {symbol:<15} ERROR: {e}")

        time.sleep(delay)

    return results


def print_results(results: list[dict], top_n: int):
    """Print ranked results table."""
    ranked = sorted(results, key=lambda r: r["test_pnl_pct"], reverse=True)[:top_n]

    print("\n" + "=" * 110)
    print(f"  TOP {len(ranked)} RESULTS (ranked by test P&L%)")
    print("=" * 110)
    print(
        f"  {'#':>3}  {'Symbol':<15} {'Train%':>8} {'Test%':>8} "
        f"{'Trades':>7} {'Win%':>6} {'DD%':>6} {'Sharpe':>7} "
        f"{'Min':>12} {'Max':>12} {'Lvl':>4} {'Sell%':>6}"
    )
    print("-" * 110)

    for i, r in enumerate(ranked, 1):
        color = "\033[32m" if r["test_pnl_pct"] > 0 else "\033[31m"
        reset = "\033[0m"
        print(
            f"  {i:>3}  {r['symbol']:<15} "
            f"{r['train_pnl_pct']:>+7.2f}% "
            f"{color}{r['test_pnl_pct']:>+7.2f}%{reset} "
            f"{r['trades']:>7} "
            f"{r['win_rate']*100:>5.1f}% "
            f"{r['max_drawdown']*100:>5.1f}% "
            f"{r['sharpe']:>7.1f} "
            f"{r['min_price']:>12.6g} "
            f"{r['max_price']:>12.6g} "
            f"{r['grid_levels']:>4} "
            f"{r['sell_pct']:>5.1f}%"
        )

    print("=" * 110)


def save_csv(results: list[dict], path: str):
    """Export results to CSV."""
    ranked = sorted(results, key=lambda r: r["test_pnl_pct"], reverse=True)
    if not ranked:
        return

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=ranked[0].keys())
        writer.writeheader()
        writer.writerows(ranked)

    print(f"\nResults saved to {path}")


def main():
    parser = argparse.ArgumentParser(description="Jobot Market Screening CLI")
    parser.add_argument("--source", choices=["api", "vision"], default="api",
                        help="Data source: 'api' (Binance API) or 'vision' (Binance Vision archives, supports 1s)")
    parser.add_argument("--interval", default="1m", help="Kline interval (default: 1m)")
    parser.add_argument("--limit", type=int, default=10080, help="Number of candles for API source (default: 10080)")
    parser.add_argument("--days", type=int, default=7, help="Number of past days for Vision source (default: 7)")
    parser.add_argument("--amount", type=float, default=1000.0, help="Simulated budget in USDC (default: 1000)")
    parser.add_argument("--top", type=int, default=50, help="Show top N results (default: 50)")
    parser.add_argument("--delay", type=float, default=0.3, help="Delay between API calls in seconds (default: 0.3)")
    parser.add_argument("--symbol", type=str, default=None, help="Test a single symbol (e.g., BTCUSDC)")
    parser.add_argument("--csv", type=str, default=None, help="Export results to CSV file")
    args = parser.parse_args()

    print(f"\nJobot Market Screening")
    if args.source == "vision":
        print(f"  Source: Binance Vision  |  Interval: {args.interval}  |  Days: {args.days}  |  Budget: ${args.amount}")
    else:
        print(f"  Source: Binance API  |  Interval: {args.interval}  |  Candles: {args.limit}  |  Budget: ${args.amount}")
    print()

    if args.symbol:
        symbols = [args.symbol.upper()]
        print(f"  Single symbol mode: {symbols[0]}")
    else:
        print("  Fetching USDC symbols from Binance...")
        symbols = get_usdc_symbols()
        print(f"  Found {len(symbols)} USDC pairs\n")

    t_start = time.time()
    results = run_screening(
        symbols, args.interval, args.limit, args.amount, args.delay,
        source=args.source, days=args.days,
    )
    elapsed = time.time() - t_start

    print(f"\n  Completed: {len(results)}/{len(symbols)} symbols in {elapsed:.0f}s")

    if results:
        print_results(results, args.top)

    if args.csv:
        save_csv(results, args.csv)


if __name__ == "__main__":
    main()
