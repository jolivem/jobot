from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.api.deps import get_current_user
from app.schemas.trading_bot import TradingBotCreate, TradingBotUpdate, TradingBotRead
from app.schemas.trade import TradeRead
from app.services.trading_bot_service import TradingBotService
from app.repositories.trade_repo import TradeRepository

router = APIRouter(prefix="/trading-bots", tags=["trading-bots"])


@router.post("", response_model=TradingBotRead)
def create_bot(
    payload: TradingBotCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    try:
        return TradingBotService(db).create(
            user_id=user.id,
            symbol=payload.symbol,
            max_price=payload.max_price,
            min_price=payload.min_price,
            total_amount=payload.total_amount,
            sell_percentage=payload.sell_percentage,
            buy_percentage=payload.buy_percentage,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=list[TradingBotRead])
def list_bots(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return TradingBotService(db).list(user.id)


@router.get("/{bot_id}", response_model=TradingBotRead)
def get_bot(bot_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    bot = TradingBotService(db).get(user.id, bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Trading bot not found")
    return bot


@router.patch("/{bot_id}", response_model=TradingBotRead)
def update_bot(
    bot_id: int,
    payload: TradingBotUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    try:
        bot = TradingBotService(db).update(
            user_id=user.id,
            bot_id=bot_id,
            symbol=payload.symbol,
            max_price=payload.max_price,
            min_price=payload.min_price,
            total_amount=payload.total_amount,
            sell_percentage=payload.sell_percentage,
            buy_percentage=payload.buy_percentage,
            is_active=payload.is_active,
        )
        if not bot:
            raise HTTPException(status_code=404, detail="Trading bot not found")
        return bot
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{bot_id}/deactivate", response_model=TradingBotRead)
def deactivate_bot(
    bot_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    bot = TradingBotService(db).deactivate(user.id, bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Trading bot not found")
    return bot


@router.delete("/{bot_id}")
def delete_bot(
    bot_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    ok = TradingBotService(db).delete(user.id, bot_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Trading bot not found")
    return {"deleted": True}


@router.get("/{bot_id}/trades", response_model=list[TradeRead])
def list_trades(
    bot_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    bot = TradingBotService(db).get(user.id, bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Trading bot not found")
    return TradeRepository(db).list_by_bot(bot_id)
