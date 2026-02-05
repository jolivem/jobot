from sqlalchemy.orm import Session
from app.repositories.trading_bot_repo import TradingBotRepository


class TradingBotService:
    def __init__(self, db: Session):
        self.repo = TradingBotRepository(db)

    def _validate_prices(self, min_price: float, max_price: float):
        if min_price >= max_price:
            raise ValueError("min_price must be less than max_price")

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
        return self.repo.create(
            user_id=user_id,
            symbol=symbol,
            max_price=max_price,
            min_price=min_price,
            total_amount=total_amount,
            sell_percentage=sell_percentage,
            buy_percentage=buy_percentage,
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

        new_min = min_price if min_price is not None else bot.min_price
        new_max = max_price if max_price is not None else bot.max_price
        self._validate_prices(new_min, new_max)

        return self.repo.update(
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

    def deactivate(self, user_id: int, bot_id: int):
        return self.repo.deactivate(user_id, bot_id)

    def delete(self, user_id: int, bot_id: int) -> bool:
        return self.repo.delete(user_id, bot_id)
