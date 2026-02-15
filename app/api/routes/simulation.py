"""Simulation and screening API endpoints."""

import time
import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.cache import RedisCache
from app.api.deps import get_current_user
from app.schemas.simulation import (
    SimulationRequest,
    SimulationResponse,
    BacktestMetrics,
    ScreeningRequest,
    ScreeningLaunchResponse,
    ScreeningStatusResponse,
)
from app.repositories.trading_bot_repo import TradingBotRepository
from app.services.klines_fetcher import fetch_klines
from app.services.parameter_optimizer import optimize_parameters
from app.services.backtest_engine import BacktestResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/simulation", tags=["simulation"])


def _to_metrics(r: BacktestResult) -> BacktestMetrics:
    return BacktestMetrics(
        total_pnl=r.total_pnl,
        total_pnl_pct=r.total_pnl_pct,
        num_trades=r.num_trades,
        num_buys=r.num_buys,
        num_sells=r.num_sells,
        win_rate=r.win_rate,
        max_drawdown=r.max_drawdown,
        sharpe_ratio=r.sharpe_ratio,
        final_open_positions=r.final_open_positions,
        unrealized_pnl=r.unrealized_pnl,
        min_price=r.min_price,
        max_price=r.max_price,
        grid_levels=r.grid_levels,
        sell_percentage=r.sell_percentage,
        total_amount=r.total_amount,
    )


@router.post("/bot/{bot_id}", response_model=SimulationResponse)
def simulate_bot(
    bot_id: int,
    payload: SimulationRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Optimize grid parameters for a specific bot's symbol.

    Synchronous endpoint. Fetches klines, runs parameter optimization,
    and returns results. Typically completes in 2-5 seconds.
    """
    bot = TradingBotRepository(db).get_by_id(user.id, bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Trading bot not found")

    start_ms = int(time.time() * 1000)

    try:
        klines = fetch_klines(
            symbol=bot.symbol,
            interval=payload.interval,
            limit=payload.limit,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch klines from Binance: {e}")

    if len(klines) < 100:
        raise HTTPException(status_code=400, detail=f"Insufficient historical data ({len(klines)} candles)")

    close_prices = [k["close"] for k in klines]

    try:
        result = optimize_parameters(
            symbol=bot.symbol,
            close_prices=close_prices,
            total_amount=payload.total_amount,
            train_ratio=payload.train_ratio,
            grid_levels_options=payload.grid_levels_options,
            sell_percentage_options=payload.sell_percentage_options,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    elapsed = int(time.time() * 1000) - start_ms

    return SimulationResponse(
        symbol=bot.symbol,
        best_params=_to_metrics(result.best_params),
        test_result=_to_metrics(result.test_result),
        top_results=[_to_metrics(r) for r in result.all_results],
        train_size=result.train_size,
        test_size=result.test_size,
        kline_interval=payload.interval,
        computed_in_ms=elapsed,
    )


@router.post("/screening", response_model=ScreeningLaunchResponse)
def launch_screening(
    payload: ScreeningRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Launch a background screening of all USDC pairs.

    Returns a task_id for polling progress via GET /simulation/screening/{task_id}.
    """
    from app.workers.celery_app import celery

    task = celery.send_task(
        "app.workers.screening_tasks.run_screening",
        args=[user.id, payload.interval, payload.limit, payload.total_amount],
    )

    return ScreeningLaunchResponse(
        task_id=task.id,
        message="Screening launched. Poll /simulation/screening/{task_id} for results.",
    )


@router.get("/screening/{task_id}", response_model=ScreeningStatusResponse)
def get_screening_status(
    task_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Poll screening task progress and results."""
    cache = RedisCache()
    key = f"screening:{task_id}"
    data = cache.client.get(key)

    if not data:
        from app.workers.celery_app import celery
        result = celery.AsyncResult(task_id)
        if result.state == "PENDING":
            return ScreeningStatusResponse(
                task_id=task_id,
                status="pending",
                progress=0,
                total_symbols=0,
                processed_symbols=0,
                results=[],
            )
        raise HTTPException(status_code=404, detail="Screening task not found")

    return ScreeningStatusResponse(**json.loads(data))
