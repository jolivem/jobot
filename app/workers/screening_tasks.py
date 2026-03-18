"""Background Celery tasks for full-market screening."""

import json
import time
import logging
from datetime import datetime, date, timedelta, timezone

from app.workers.celery_app import celery
from app.core.cache import RedisCache
from app.services.binance_price_service import BinancePriceService
from app.services.klines_fetcher import fetch_klines_by_day
from app.services.klines_store import get_missing_days, load_days, save_day
from app.services.parameter_optimizer import (
    optimize_parameters,
    SCREENING_GRID_LEVELS,
    SCREENING_SELL_PERCENTAGES,
)
from app.core.db import SessionLocal
from app.models.screening_result import ScreeningResult

logger = logging.getLogger(__name__)

BATCH_DELAY = 0.5  # seconds between Binance API calls (rate limiting)


@celery.task(name="app.workers.screening_tasks.run_screening", bind=True, acks_late=True)
def run_screening(
    self,
    user_id: int,
    interval: str = "1h",
    days: int = 7,
    total_amount: float = 1000.0,
):
    """Screen all USDC pairs for grid trading profitability.

    For each symbol:
    1. Check local klines cache, fetch missing days from Binance.
    2. Run parameter optimization (reduced grid for speed).
    3. Store incremental progress in Redis for polling.
    4. Store final results in database.
    """
    task_id = self.request.id
    cache = RedisCache()
    redis_key = f"screening:{task_id}"

    # Get all USDC symbols
    cached_symbols = cache.get_symbols("USDC")
    if cached_symbols:
        symbols = cached_symbols
    else:
        binance = BinancePriceService()
        symbols = binance.get_usdc_symbols()

    total = len(symbols)
    results: list[dict] = []
    started_at = datetime.now(timezone.utc).isoformat()

    # Compute screening dates: yesterday back to N days ago
    today = datetime.now(timezone.utc).date()
    dates = [today - timedelta(days=d) for d in range(days, 0, -1)]

    def update_progress(processed: int, status: str = "running"):
        progress_data = {
            "task_id": task_id,
            "status": status,
            "progress": int(processed / total * 100) if total > 0 else 0,
            "total_symbols": total,
            "processed_symbols": processed,
            "results": sorted(results, key=lambda r: r["best_pnl_pct"], reverse=True)[:50],
            "started_at": started_at,
            "completed_at": datetime.now(timezone.utc).isoformat() if status == "completed" else None,
        }
        cache.client.setex(redis_key, 3600, json.dumps(progress_data))

    update_progress(0)
    logger.info(f"Screening {task_id}: starting on {total} symbols, {len(dates)} days ({dates[0]} to {dates[-1]})")

    for i, symbol in enumerate(symbols):
        try:
            # Fetch and store missing days
            missing = get_missing_days(symbol, interval, dates)
            for day in missing:
                klines = fetch_klines_by_day(symbol=symbol, interval=interval, day=day)
                if klines:
                    save_day(symbol, interval, day, klines)
                time.sleep(BATCH_DELAY)

            # Load all days from local storage
            klines = load_days(symbol, interval, dates)

            if len(klines) < 200:
                logger.debug(f"Screening: skipping {symbol} ({len(klines)} klines)")
                update_progress(i + 1)
                continue

            close_prices = [k["close"] for k in klines]

            opt = optimize_parameters(
                symbol=symbol,
                close_prices=close_prices,
                total_amount=total_amount,
                grid_levels_options=SCREENING_GRID_LEVELS,
                sell_percentage_options=SCREENING_SELL_PERCENTAGES,
            )

            results.append({
                "symbol": symbol,
                "best_pnl_pct": opt.best_params.total_pnl_pct,
                "best_min_price": opt.best_params.min_price,
                "best_max_price": opt.best_params.max_price,
                "best_grid_levels": opt.best_params.grid_levels,
                "best_sell_percentage": opt.best_params.sell_percentage,
                "num_trades": opt.best_params.num_trades,
                "win_rate": opt.best_params.win_rate,
                "max_drawdown": opt.best_params.max_drawdown,
                "sharpe_ratio": opt.best_params.sharpe_ratio,
            })

        except Exception as e:
            logger.warning(f"Screening: failed on {symbol}: {e}")

        update_progress(i + 1)

    # Persist final results to database
    db = SessionLocal()
    try:
        for r in results:
            row = ScreeningResult(
                task_id=task_id,
                user_id=user_id,
                **r,
            )
            db.add(row)
        db.commit()
        logger.info(f"Screening {task_id}: saved {len(results)} results to database")
    except Exception as e:
        logger.error(f"Screening {task_id}: failed to persist results: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()

    update_progress(total, status="completed")
    logger.info(f"Screening {task_id} completed: {len(results)}/{total} symbols processed")
