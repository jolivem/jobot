import logging
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.config import settings
from app.api.deps import get_current_user
from app.schemas.trading_bot import TradingBotCreate, TradingBotUpdate, TradingBotRead, BotStats
from app.schemas.trade import TradeRead, TradeWithSymbol
from app.services.trading_bot_service import TradingBotService
from app.services.binance_trade_service import BinanceTradeService
from app.repositories.trading_bot_repo import TradingBotRepository
from app.repositories.trade_repo import TradeRepository
from app.core.cache import RedisCache

logger = logging.getLogger(__name__)

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

    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    results = []
    for bot in bots:
        trades = trade_repo.list_by_bot(bot.id)
        # Sort chronologically (oldest first) for FIFO matching
        trades.sort(key=lambda t: t.created_at)

        buys = []
        realized_profit = 0.0
        monthly_realized_profit = 0.0
        for t in trades:
            if t.trade_type == "buy":
                buys.append(t)
            elif t.trade_type == "sell" and buys:
                buy = buys.pop(0)
                profit = (t.price - buy.price) * t.quantity
                realized_profit += profit
                if t.created_at >= month_start:
                    monthly_realized_profit += profit

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
            monthly_realized_profit=round(monthly_realized_profit, 6),
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


@router.post("/{bot_id}/emergency-sell")
def emergency_sell(
    bot_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    """Sell all open positions for a bot at market price."""
    bot = TradingBotService(db).get(user.id, bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Trading bot not found")

    # Compute open positions via FIFO matching
    trade_repo = TradeRepository(db)
    trades = trade_repo.list_by_bot(bot_id)
    trades.sort(key=lambda t: t.created_at)

    buys: list = []
    for t in trades:
        if t.trade_type == "buy":
            buys.append(t)
        elif t.trade_type == "sell" and buys:
            buys.pop(0)

    if not buys:
        raise HTTPException(status_code=400, detail="No open positions to sell")

    # Get current market price
    try:
        cache = RedisCache()
        current_price = cache.get_price(bot.symbol)
    except Exception:
        current_price = None

    if current_price is None:
        raise HTTPException(status_code=503, detail="Current price unavailable")

    # Place real Binance orders if live trading is enabled
    if settings.BINANCE_LIVE_TRADING and user.binance_api_key and user.binance_api_secret:
        binance = BinanceTradeService(user.binance_api_key, user.binance_api_secret)
        total_qty = sum(b.quantity for b in buys)
        try:
            binance.place_order(bot.symbol, "SELL", total_qty)
        except Exception as e:
            logger.error(f"Emergency sell Binance order failed for bot {bot_id}: {e}")
            raise HTTPException(status_code=502, detail=f"Binance order failed: {e}")

    # Record sell trades in DB
    sold = []
    for buy in buys:
        trade = trade_repo.create(
            trading_bot_id=bot_id,
            trade_type="sell",
            price=current_price,
            quantity=buy.quantity,
        )
        sold.append(trade)

    # Clear bot state in Redis and deactivate
    try:
        cache = RedisCache()
        cache.delete_bot_state(bot_id)
    except Exception:
        pass

    TradingBotService(db).deactivate(user.id, bot_id)

    return {"sold_count": len(sold), "price": current_price}


@router.get("/{bot_id}/trades", response_model=list[TradeRead])
def list_trades(
    bot_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    bot = TradingBotService(db).get(user.id, bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Trading bot not found")
    return TradeRepository(db).list_by_bot(bot_id)


@router.get("/{bot_id}/klines")
def get_klines(
    bot_id: int,
    interval: str = "1h",
    limit: int = 168,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Fetch candlestick data from Binance for a bot's symbol."""
    allowed_intervals = {"1m","3m","5m","15m","30m","1h","2h","4h","6h","8h","12h","1d","3d","1w","1M"}
    if interval not in allowed_intervals:
        raise HTTPException(status_code=400, detail=f"Invalid interval: {interval}")
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 1000")

    bot = TradingBotService(db).get(user.id, bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Trading bot not found")

    url = f"{settings.BINANCE_BASE_URL}/api/v3/klines"
    params = {"symbol": bot.symbol, "interval": interval, "limit": limit}

    try:
        resp = httpx.get(url, params=params, timeout=10)
        resp.raise_for_status()
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Failed to fetch klines from Binance")

    return [
        {
            "time": int(k[0] / 1000),  # ms -> seconds for lightweight-charts
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
        }
        for k in resp.json()
    ]
