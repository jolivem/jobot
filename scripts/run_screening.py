#!/usr/bin/env python3
"""Standalone CLI screening script.

Scans all Binance USDC pairs, runs grid parameter optimization on each,
and outputs the results ranked by P&L%. No frontend, Redis, or DB needed.

Klines are cached locally as JSON files (one file per day/symbol/interval).
Only missing days are fetched from Binance. The current day is never included
(screening operates on complete days only).

Usage:
    python scripts/run_screening.py
    python scripts/run_screening.py --interval 1m --days 7 --top 30
    python scripts/run_screening.py --symbol BTCUSDC
    python scripts/run_screening.py --csv results.csv
    python scripts/run_screening.py --clear-cache
"""

import os
import sys
import time
import shutil
import argparse
import csv
from datetime import date, timedelta, timezone, datetime

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

from app.services.klines_fetcher import fetch_klines_by_day
from app.services.klines_store import (
    get_missing_days,
    load_days,
    save_day,
)
from app.services.parameter_optimizer import (
    optimize_parameters,
    SCREENING_GRID_LEVELS,
    SCREENING_SELL_PERCENTAGES,
)
from app.services.binance_price_service import BinancePriceService
from app.services.market_stats import compute_market_stats


def get_usdc_symbols() -> list[str]:
    """Fetch all USDC trading pairs from Binance."""
    return BinancePriceService().get_usdc_symbols()


def compute_screening_dates(days: int) -> list[date]:
    """Return the list of dates to screen: [today - days, ..., yesterday]."""
    today = datetime.now(timezone.utc).date()
    return [today - timedelta(days=d) for d in range(days, 0, -1)]


def fetch_and_store_missing(
    symbol: str,
    interval: str,
    dates: list[date],
    delay: float,
    no_cache: bool = False,
) -> int:
    """Fetch missing days from Binance and store locally.

    Returns the number of API calls made.
    """
    if no_cache:
        missing = dates
    else:
        missing = get_missing_days(symbol, interval, dates)

    if not missing:
        return 0

    for day in missing:
        klines = fetch_klines_by_day(symbol=symbol, interval=interval, day=day)
        if klines:
            save_day(symbol, interval, day, klines)
        time.sleep(delay)

    return len(missing)


def run_screening(
    symbols: list[str],
    interval: str,
    days: int,
    total_amount: float,
    delay: float,
    no_cache: bool = False,
) -> list[dict]:
    """Run optimization on each symbol and return results."""
    results = []
    total = len(symbols)
    dates = compute_screening_dates(days)

    print(f"  Screening period: {dates[0]} to {dates[-1]} ({len(dates)} days)")
    print()

    for i, symbol in enumerate(symbols, 1):
        progress = f"[{i}/{total}]"
        try:
            api_calls = fetch_and_store_missing(
                symbol, interval, dates, delay, no_cache,
            )

            klines = load_days(symbol, interval, dates)

            if len(klines) < 200:
                cache_info = "fetched" if api_calls else "cached"
                print(f"  {progress} {symbol:<15} skipped ({len(klines)} candles, {cache_info})")
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

            stats = compute_market_stats(klines)
            cum_buy_vol = sum(k.get("buy_quote_volume", 0.0) for k in klines)

            r = {
                "symbol": symbol,
                "pnl_pct": opt.best_params.total_pnl_pct,
                "trades": opt.best_params.num_trades,
                "win_rate": opt.best_params.win_rate,
                "max_drawdown": opt.best_params.max_drawdown,
                "sharpe": opt.best_params.sharpe_ratio,
                "trend_pct": stats["trend_pct"],
                "volatility_pct": stats["volatility_pct"],
                "range_pct": stats["range_pct"],
                "stddev_pct": stats["stddev_pct"],
                "adr_pct": stats["adr_pct"],
                "mean_reversion": stats["mean_reversion"],
                "cum_buy_vol": cum_buy_vol,
                "min_price": opt.best_params.min_price,
                "max_price": opt.best_params.max_price,
                "grid_levels": opt.best_params.grid_levels,
                "sell_pct": opt.best_params.sell_percentage,
            }
            results.append(r)

            color = "\033[32m" if r["pnl_pct"] > 0 else "\033[31m"
            reset = "\033[0m"
            tr_color = "\033[32m" if r["trend_pct"] > 0 else "\033[31m"
            mr_color = "\033[32m" if r["mean_reversion"] < 0 else "\033[33m"
            cache_info = f"fetched {api_calls}d" if api_calls else "cached"
            print(
                f"  {progress} {symbol:<15} {len(klines):>7} candles ({cache_info})  "
                f"P&L: {color}{r['pnl_pct']:+7.2f}%{reset}  "
                f"trades: {r['trades']:>4}  "
                f"win: {r['win_rate']*100:5.1f}%  "
                f"trend: {tr_color}{r['trend_pct']:+5.1f}%{reset}  "
                f"vol: {r['volatility_pct']:>4.0f}%  "
                f"rng: {r['range_pct']:>5.1f}%  "
                f"adr: {r['adr_pct']:>5.2f}%  "
                f"mr: {mr_color}{r['mean_reversion']:+.3f}{reset}  "
                f"({elapsed:.1f}s)"
            )

        except Exception as e:
            print(f"  {progress} {symbol:<15} ERROR: {e}")

    return results


def print_results(results: list[dict], top_n: int):
    """Print ranked results table."""
    ranked = sorted(results, key=lambda r: r["pnl_pct"], reverse=True)[:top_n]

    w = 161
    print("\n" + "=" * w)
    print(f"  TOP {len(ranked)} RESULTS (ranked by P&L%)")
    print("=" * w)
    print(
        f"  {'#':>3}  {'Symbol':<15} {'P&L%':>8} "
        f"{'Trades':>7} {'Win%':>6} {'DD%':>6} {'Sharpe':>7} "
        f"{'Trend%':>7} {'Vol%':>8} {'Range%':>7} {'Std%':>6} {'ADR%':>7} {'MnRev':>6} "
        f"{'BuyVol':>14} "
        f"{'Lvl':>4} {'Sell%':>6}"
    )
    print("-" * w)

    for i, r in enumerate(ranked, 1):
        color = "\033[32m" if r["pnl_pct"] > 0 else "\033[31m"
        reset = "\033[0m"
        tr_color = "\033[32m" if r["trend_pct"] > 0 else "\033[31m"
        mr_color = "\033[32m" if r["mean_reversion"] < 0 else "\033[33m"
        print(
            f"  {i:>3}  {r['symbol']:<15} "
            f"{color}{r['pnl_pct']:>+7.2f}%{reset} "
            f"{r['trades']:>7} "
            f"{r['win_rate']*100:>5.1f}% "
            f"{r['max_drawdown']*100:>5.1f}% "
            f"{r['sharpe']:>7.1f} "
            f"{tr_color}{r['trend_pct']:>+6.1f}%{reset} "
            f"{r['volatility_pct']:>7.0f}% "
            f"{r['range_pct']:>6.1f}% "
            f"{r['stddev_pct']:>5.1f}% "
            f"{r['adr_pct']:>6.2f}% "
            f"{mr_color}{r['mean_reversion']:>+5.3f}{reset} "
            f"{r.get('cum_buy_vol', 0.0):>14.0f} "
            f"{r['grid_levels']:>4} "
            f"{r['sell_pct']:>5.1f}%"
        )

    print("=" * w)


def save_csv(results: list[dict], path: str):
    """Export results to CSV."""
    ranked = sorted(results, key=lambda r: r["pnl_pct"], reverse=True)
    if not ranked:
        return

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=ranked[0].keys())
        writer.writeheader()
        writer.writerows(ranked)

    print(f"\nResults saved to {path}")


def main():
    parser = argparse.ArgumentParser(description="Jobot Market Screening CLI")
    parser.add_argument("--interval", default="1m", help="Kline interval (default: 1m)")
    parser.add_argument("--days", type=int, default=7, help="Number of past days to screen (default: 7)")
    parser.add_argument("--amount", type=float, default=1000.0, help="Simulated budget in USDC (default: 1000)")
    parser.add_argument("--top", type=int, default=50, help="Show top N results (default: 50)")
    parser.add_argument("--delay", type=float, default=0.3, help="Delay between API calls in seconds (default: 0.3)")
    parser.add_argument("--symbol", type=str, default=None, help="Test a single symbol (e.g., BTCUSDC)")
    parser.add_argument("--csv", type=str, default=None, help="Export results to CSV file")
    parser.add_argument("--no-cache", action="store_true", help="Force re-fetch all days from Binance")
    parser.add_argument("--clear-cache", action="store_true", help="Delete all local klines data and exit")
    parser.add_argument("--data-dir", type=str, default=None,
                        help="Override klines data directory (default: from KLINES_DATA_DIR setting)")
    args = parser.parse_args()

    # Override data dir if provided
    if args.data_dir:
        from app.core.config import settings
        settings.KLINES_DATA_DIR = args.data_dir

    # Handle --clear-cache
    if args.clear_cache:
        from app.core.config import settings
        data_dir = settings.KLINES_DATA_DIR
        if os.path.exists(data_dir):
            shutil.rmtree(data_dir)
            print(f"Cleared klines cache: {data_dir}")
        else:
            print(f"No cache to clear: {data_dir}")
        return

    print(f"\nJobot Market Screening")
    print(f"  Interval: {args.interval}  |  Days: {args.days}  |  Budget: ${args.amount}")
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
        symbols, args.interval, args.days, args.amount, args.delay,
        no_cache=args.no_cache,
    )
    elapsed = time.time() - t_start

    print(f"\n  Completed: {len(results)}/{len(symbols)} symbols in {elapsed:.0f}s")

    if results:
        print_results(results, args.top)

    if args.csv:
        save_csv(results, args.csv)


if __name__ == "__main__":
    main()
