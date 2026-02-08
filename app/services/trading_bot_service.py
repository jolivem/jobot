from sqlalchemy.orm import Session
from app.repositories.trading_bot_repo import TradingBotRepository
from app.repositories.trade_repo import TradeRepository
from app.core.cache import RedisCache
from app.workers.celery_app import celery


class TradingBotService:
    def __init__(self, db: Session):
        self.repo = TradingBotRepository(db)

    def _validate_prices(self, min_price: float, max_price: float):
        if min_price >= max_price:
            raise ValueError("min_price must be less than max_price")

    def _launch_bot_task(self, bot_id: int):
        """Launch a long-running Celery task for this bot"""
        celery.send_task("app.workers.tasks.run_trading_bot", args=[bot_id])

    def create(
        self,
        user_id: int,
        symbol: str,
        max_price: float,
        min_price: float,
        total_amount: float,
        sell_percentage: float,
        buy_percentage: float,
    ):
        self._validate_prices(min_price, max_price)
        bot = self.repo.create(
            user_id=user_id,
            symbol=symbol,
            max_price=max_price,
            min_price=min_price,
            total_amount=total_amount,
            sell_percentage=sell_percentage,
            buy_percentage=buy_percentage,
        )
        self._launch_bot_task(bot.id)
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
        buy_percentage: float | None = None,
        is_active: int | None = None,
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
            buy_percentage=buy_percentage,
            is_active=is_active,
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
        # Delete associated trades first (foreign key constraint)
        TradeRepository(self.repo.db).delete_by_bot(bot_id)
        # Clean up Redis state
        try:
            RedisCache().delete_bot_state(bot_id)
        except Exception:
            pass
        return self.repo.delete(user_id, bot_id)
