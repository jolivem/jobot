from sqlalchemy.orm import Session
from app.repositories.lstm_bot_repo import LstmBotRepository
from app.workers.celery_app import celery


class LstmBotService:
    def __init__(self, db: Session):
        self.repo = LstmBotRepository(db)

    def _launch_bot_task(self, bot_id: int):
        celery.send_task("app.workers.lstm_tasks.run_lstm_bot", args=[bot_id])

    def create(
        self,
        user_id: int,
        symbol: str,
        timeframes: str,
        total_amount: float,
        max_positions: int = 3,
        buy_slope_threshold: float = 0.0,
        sell_slope_threshold: float = 0.0,
        take_profit_pct: float = 2.0,
        stop_loss_pct: float = 3.0,
    ):
        return self.repo.create(
            user_id=user_id,
            symbol=symbol,
            timeframes=timeframes,
            total_amount=total_amount,
            max_positions=max_positions,
            buy_slope_threshold=buy_slope_threshold,
            sell_slope_threshold=sell_slope_threshold,
            take_profit_pct=take_profit_pct,
            stop_loss_pct=stop_loss_pct,
        )

    def list(self, user_id: int):
        return self.repo.list_by_user(user_id)

    def get(self, user_id: int, bot_id: int):
        return self.repo.get_by_id(user_id, bot_id)

    def update(
        self,
        user_id: int,
        bot_id: int,
        symbol: str | None = None,
        timeframes: str | None = None,
        total_amount: float | None = None,
        max_positions: int | None = None,
        buy_slope_threshold: float | None = None,
        sell_slope_threshold: float | None = None,
        take_profit_pct: float | None = None,
        stop_loss_pct: float | None = None,
        is_active: int | None = None,
    ):
        bot = self.repo.get_by_id(user_id, bot_id)
        if not bot:
            return None

        was_inactive = bot.is_active == 0
        updated = self.repo.update(
            user_id, bot_id,
            symbol=symbol,
            timeframes=timeframes,
            total_amount=total_amount,
            max_positions=max_positions,
            buy_slope_threshold=buy_slope_threshold,
            sell_slope_threshold=sell_slope_threshold,
            take_profit_pct=take_profit_pct,
            stop_loss_pct=stop_loss_pct,
            is_active=is_active,
        )

        if updated and was_inactive and is_active == 1:
            self._launch_bot_task(bot_id)

        return updated

    def deactivate(self, user_id: int, bot_id: int):
        return self.repo.deactivate(user_id, bot_id)

    def delete(self, user_id: int, bot_id: int) -> bool:
        bot = self.repo.get_by_id(user_id, bot_id)
        if not bot:
            return False
        return self.repo.delete(user_id, bot_id)
