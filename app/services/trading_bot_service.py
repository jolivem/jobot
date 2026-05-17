from sqlalchemy.orm import Session
from app.repositories.trading_bot_repo import TradingBotRepository
from app.repositories.trade_repo import TradeRepository
from app.repositories.pnl_snapshot_repo import PnlSnapshotRepository
from app.repositories.buy_level_repo import BuyLevelRepository
from app.repositories.deleted_bot_repo import DeletedBotRepository
from app.services.pnl_service import compute_bot_pnl
from app.core.cache import RedisCache
from app.workers.celery_app import celery


class TradingBotService:
    def __init__(self, db: Session):
        self.repo = TradingBotRepository(db)

    def _validate_prices(self, min_price: float, max_price: float):
        if min_price >= max_price:
            raise ValueError("min_price must be less than max_price")

    def _launch_bot_task(self, bot_id: int):
        """No-op: bots are now auto-detected by the unified run_all_bots loop."""
        pass

    def create(
        self,
        user_id: int,
        symbol: str,
        max_price: float,
        min_price: float,
        total_amount: float,
        sell_percentage: float,
        grid_levels: int = 10,
    ):
        self._validate_prices(min_price, max_price)
        bot = self.repo.create(
            user_id=user_id,
            symbol=symbol,
            max_price=max_price,
            min_price=min_price,
            total_amount=total_amount,
            sell_percentage=sell_percentage,
            grid_levels=grid_levels,
        )
        return bot

    def list(self, user_id: int):
        return self.repo.list_by_user(user_id)

    def get(self, user_id: int, bot_id: int):
        return self.repo.get_by_id(user_id, bot_id)

    def update(
        self,
        user_id: int,
        bot_id: int,
        symbol: str | None = None,
        max_price: float | None = None,
        min_price: float | None = None,
        total_amount: float | None = None,
        sell_percentage: float | None = None,
        grid_levels: int | None = None,
        is_active: int | None = None,
        sell_only: int | None = None,
    ):
        bot = self.repo.get_by_id(user_id, bot_id)
        if not bot:
            return None

        was_inactive = bot.is_active == 0
        new_min = min_price if min_price is not None else bot.min_price
        new_max = max_price if max_price is not None else bot.max_price
        self._validate_prices(new_min, new_max)

        updated = self.repo.update(
            user_id,
            bot_id,
            symbol=symbol,
            max_price=max_price,
            min_price=min_price,
            total_amount=total_amount,
            sell_percentage=sell_percentage,
            grid_levels=grid_levels,
            is_active=is_active,
            sell_only=sell_only,
        )

        # Launch task if bot was reactivated
        if updated and was_inactive and is_active == 1:
            self._launch_bot_task(bot_id)

        return updated

    def deactivate(self, user_id: int, bot_id: int):
        return self.repo.deactivate(user_id, bot_id)

    def delete(self, user_id: int, bot_id: int) -> bool:
        bot = self.repo.get_by_id(user_id, bot_id)
        if not bot:
            return False

        # Archive bot with P&L before deletion
        trade_repo = TradeRepository(self.repo.db)
        trades = trade_repo.list_by_bot(bot_id)
        trades.sort(key=lambda t: t.created_at)

        current_price = None
        try:
            current_price = RedisCache().get_price(bot.symbol)
        except Exception:
            pass

        pnl = compute_bot_pnl(trades, current_price)
        DeletedBotRepository(self.repo.db).create(
            user_id=user_id,
            original_bot_id=bot_id,
            symbol=bot.symbol,
            min_price=bot.min_price,
            max_price=bot.max_price,
            total_amount=bot.total_amount,
            sell_percentage=bot.sell_percentage,
            grid_levels=bot.grid_levels,
            realized_pnl=round(pnl["realized_pnl"], 6),
            total_pnl=round(pnl["total_pnl"], 6),
            created_at=bot.created_at,
        )

        # Delete associated data (foreign key constraints)
        PnlSnapshotRepository(self.repo.db).detach_bot(bot_id)
        BuyLevelRepository(self.repo.db).delete_by_bot(bot_id)
        trade_repo.delete_by_bot(bot_id)
        # Clean up Redis state
        try:
            RedisCache().delete_bot_state(bot_id)
        except Exception:
            pass
        return self.repo.delete(user_id, bot_id)
