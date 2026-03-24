import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.api.deps import get_current_user
from app.schemas.lstm_bot import LstmBotCreate, LstmBotUpdate, LstmBotRead, SlopeResponse
from app.services.lstm_bot_service import LstmBotService
from app.services.lstm_model_service import (
    predict_slopes,
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
