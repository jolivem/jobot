import logging
import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.api.deps import get_current_user
from app.schemas.lstm_bot import LstmBotCreate, LstmBotUpdate, LstmBotRead, SlopeResponse
from app.services.lstm_bot_service import LstmBotService
from app.services.lstm_model_service import (
    predict_slopes,
    predict_slope_history,
    has_model,
    save_uploaded_model,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/lstm-bots", tags=["lstm-bots"])


@router.post("", response_model=LstmBotRead)
def create_bot(
    payload: LstmBotCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    try:
        return LstmBotService(db).create(
            user_id=user.id,
            symbol=payload.symbol,
            timeframes=payload.timeframes,
            total_amount=payload.total_amount,
            max_positions=payload.max_positions,
            buy_slope_threshold=payload.buy_slope_threshold,
            sell_slope_threshold=payload.sell_slope_threshold,
            take_profit_pct=payload.take_profit_pct,
            stop_loss_pct=payload.stop_loss_pct,
        )
    except Exception as e:
        logger.exception(f"Failed to create LSTM bot: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=list[LstmBotRead])
def list_bots(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return LstmBotService(db).list(user.id)


@router.get("/{bot_id}", response_model=LstmBotRead)
def get_bot(bot_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    bot = LstmBotService(db).get(user.id, bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="LSTM bot not found")
    return bot


@router.patch("/{bot_id}", response_model=LstmBotRead)
def update_bot(
    bot_id: int,
    payload: LstmBotUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    bot = LstmBotService(db).update(
        user_id=user.id,
        bot_id=bot_id,
        symbol=payload.symbol,
        timeframes=payload.timeframes,
        total_amount=payload.total_amount,
        max_positions=payload.max_positions,
        buy_slope_threshold=payload.buy_slope_threshold,
        sell_slope_threshold=payload.sell_slope_threshold,
        take_profit_pct=payload.take_profit_pct,
        stop_loss_pct=payload.stop_loss_pct,
        is_active=payload.is_active,
    )
    if not bot:
        raise HTTPException(status_code=404, detail="LSTM bot not found")
    return bot


@router.delete("/{bot_id}")
def delete_bot(
    bot_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    try:
        ok = LstmBotService(db).delete(user.id, bot_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete LSTM bot: {e}")
    if not ok:
        raise HTTPException(status_code=404, detail="LSTM bot not found")
    return {"deleted": True}


@router.post("/{bot_id}/deactivate", response_model=LstmBotRead)
def deactivate_bot(
    bot_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    bot = LstmBotService(db).deactivate(user.id, bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="LSTM bot not found")
    return bot


@router.post("/{bot_id}/refresh-status", response_model=LstmBotRead)
def refresh_model_status(
    bot_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    """Check if models exist on disk and update model_status accordingly."""
    svc = LstmBotService(db)
    bot = svc.get(user.id, bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="LSTM bot not found")
    svc._check_models(bot.id, bot.symbol, bot.timeframes)
    return svc.get(user.id, bot_id)


@router.get("/{bot_id}/slopes", response_model=list[SlopeResponse])
def get_slopes(
    bot_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    """Get current slope predictions for all timeframes of a bot."""
    bot = LstmBotService(db).get(user.id, bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="LSTM bot not found")
    if bot.model_status != "ready":
        raise HTTPException(status_code=400, detail=f"Model not ready (status={bot.model_status})")

    timeframes = bot.timeframes.split(",")
    slopes = predict_slopes(bot.symbol, timeframes)

    results = []
    for tf in timeframes:
        slope = slopes.get(tf)
        if slope is None:
            direction = "neutral"
        elif slope > bot.buy_slope_threshold:
            direction = "up"
        elif slope < bot.sell_slope_threshold:
            direction = "down"
        else:
            direction = "neutral"
        results.append(SlopeResponse(
            timeframe=tf,
            slope=slope if slope is not None else 0.0,
            direction=direction,
        ))
    return results


@router.post("/{bot_id}/model")
async def upload_model(
    bot_id: int,
    timeframe: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Upload a trained model ZIP for a specific timeframe.

    The ZIP should contain: saved_model.keras, saved.weights.h5, meta.json
    """
    bot = LstmBotService(db).get(user.id, bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="LSTM bot not found")

    valid_timeframes = bot.timeframes.split(",")
    if timeframe not in valid_timeframes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timeframe '{timeframe}'. Valid: {valid_timeframes}",
        )

    data = await file.read()
    ok = save_uploaded_model(bot.symbol, timeframe, data)
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid model ZIP file")

    # Check if all timeframe models are now available
    from app.repositories.lstm_bot_repo import LstmBotRepository
    all_ready = all(has_model(bot.symbol, tf) for tf in valid_timeframes)
    if all_ready:
        LstmBotRepository(db).set_model_status(bot_id, "ready")

    return {"uploaded": True, "timeframe": timeframe, "all_models_ready": all_ready}


@router.get("/{bot_id}/klines")
def get_klines(
    bot_id: int,
    interval: str = "1h",
    limit: int = 168,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Fetch candlestick data from Binance for an LSTM bot's symbol."""
    from app.core.config import settings

    allowed_intervals = {"1m","3m","5m","15m","30m","1h","2h","4h","6h","8h","12h","1d","3d","1w","1M"}
    if interval not in allowed_intervals:
        raise HTTPException(status_code=400, detail=f"Invalid interval: {interval}")
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 1000")

    bot = LstmBotService(db).get(user.id, bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="LSTM bot not found")

    url = f"{settings.BINANCE_BASE_URL}/api/v3/klines"
    params = {"symbol": bot.symbol, "interval": interval, "limit": limit}

    try:
        resp = httpx.get(url, params=params, timeout=10)
        resp.raise_for_status()
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Failed to fetch klines from Binance")

    klines = [
        {
            "time": int(k[0] / 1000),
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
        }
        for k in resp.json()
    ]
    return klines


@router.get("/{bot_id}/slope-history")
def get_slope_history(
    bot_id: int,
    limit: int = 168,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Return predicted slope history for each model timeframe.

    Each model fetches klines at its own interval (e.g. 15m model uses 15m
    klines, 1d model uses 1d klines) so each prediction matches the model's
    native timeframe.
    """
    from app.services.klines_fetcher import fetch_klines as fetch

    bot = LstmBotService(db).get(user.id, bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="LSTM bot not found")
    if bot.model_status != "ready":
        raise HTTPException(status_code=400, detail=f"Model not ready (status={bot.model_status})")

    timeframes = bot.timeframes.split(",")
    result = {}
    for tf in timeframes:
        # Each model uses its own timeframe klines
        klines = fetch(bot.symbol, interval=tf, limit=limit + 100)
        history = predict_slope_history(bot.symbol, tf, klines)
        result[tf] = history or []

    return result
