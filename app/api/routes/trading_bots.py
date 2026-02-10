from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.api.deps import get_current_user
from app.schemas.trading_bot import TradingBotCreate, TradingBotUpdate, TradingBotRead, BotStats
from app.schemas.trade import TradeRead, TradeWithSymbol
from app.services.trading_bot_service import TradingBotService
from app.repositories.trading_bot_repo import TradingBotRepository
from app.repositories.trade_repo import TradeRepository
from app.core.cache import RedisCache

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
            grid_levels=payload.grid_levels,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=list[TradingBotRead])
def list_bots(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return TradingBotService(db).list(user.id)


@router.get("/stats", response_model=list[BotStats])
def bot_stats(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Compute realized profit and open positions value for all user bots."""
    bots = TradingBotService(db).list(user.id)
    if not bots:
        return []

    trade_repo = TradeRepository(db)
    try:
        cache = RedisCache()
    except Exception:
        cache = None

    results = []
    for bot in bots:
        trades = trade_repo.list_by_bot(bot.id)
        # Sort chronologically (oldest first) for FIFO matching
        trades.sort(key=lambda t: t.created_at)

        buys = []
        realized_profit = 0.0
        for t in trades:
            if t.trade_type == "buy":
                buys.append(t)
            elif t.trade_type == "sell" and buys:
                buy = buys.pop(0)
                realized_profit += (t.price - buy.price) * t.quantity

        # Open positions = remaining unmatched buys
        open_cost = sum(b.price * b.quantity for b in buys)

        # Current price from Redis
        current_price = None
        open_value = None
        if cache:
            try:
                current_price = cache.get_price(bot.symbol)
            except Exception:
                pass
        if current_price is not None:
            open_value = sum(b.quantity * current_price for b in buys)

        results.append(BotStats(
            bot_id=bot.id,
            symbol=bot.symbol,
            realized_profit=round(realized_profit, 6),
            open_positions_count=len(buys),
            open_positions_cost=round(open_cost, 6),
            current_price=current_price,
            open_positions_value=round(open_value, 6) if open_value is not None else None,
        ))

    return results


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
            grid_levels=payload.grid_levels,
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


@router.get("/trades/all", response_model=list[TradeWithSymbol])
def list_all_trades(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """List recent trades across all user's bots."""
    bots = TradingBotService(db).list(user.id)
    if not bots:
        return []
    bot_map = {b.id: b.symbol for b in bots}
    trades = TradeRepository(db).list_by_bots(list(bot_map.keys()))
    return [
        TradeWithSymbol(
            id=t.id,
            trading_bot_id=t.trading_bot_id,
            trade_type=t.trade_type,
            price=t.price,
            quantity=t.quantity,
            created_at=t.created_at,
            symbol=bot_map[t.trading_bot_id],
        )
        for t in trades
    ]


@router.get("/{bot_id}/trades", response_model=list[TradeRead])
def list_trades(
    bot_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    bot = TradingBotService(db).get(user.id, bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Trading bot not found")
    return TradeRepository(db).list_by_bot(bot_id)
