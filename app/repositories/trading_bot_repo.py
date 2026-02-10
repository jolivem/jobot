from sqlalchemy.orm import Session, joinedload
from app.models.trading_bot import TradingBot
from app.models.user import User


class TradingBotRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        user_id: int,
        symbol: str,
        max_price: float,
        min_price: float,
        total_amount: float,
        sell_percentage: float,
        grid_levels: int = 10,
    ) -> TradingBot:
        row = TradingBot(
            user_id=user_id,
            symbol=symbol.upper().strip(),
            max_price=max_price,
            min_price=min_price,
            total_amount=total_amount,
            sell_percentage=sell_percentage,
            grid_levels=grid_levels,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def update(self, user_id: int, bot_id: int, **kwargs) -> TradingBot | None:
        row = self.get_by_id(user_id, bot_id)
        if not row:
            return None
        for key, value in kwargs.items():
            if value is not None and hasattr(row, key):
                if key == "symbol":
                    value = value.upper().strip()
                setattr(row, key, value)
        self.db.commit()
        self.db.refresh(row)
        return row

    def list_by_user(self, user_id: int) -> list[TradingBot]:
        return (
            self.db.query(TradingBot)
            .filter(TradingBot.user_id == user_id)
            .order_by(TradingBot.id.desc())
            .all()
        )

    def get_by_id(self, user_id: int, bot_id: int) -> TradingBot | None:
        return (
            self.db.query(TradingBot)
            .filter(TradingBot.user_id == user_id, TradingBot.id == bot_id)
            .first()
        )

    def deactivate(self, user_id: int, bot_id: int) -> TradingBot | None:
        row = self.get_by_id(user_id, bot_id)
        if not row:
            return None
        row.is_active = 0
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, user_id: int, bot_id: int) -> bool:
        row = self.get_by_id(user_id, bot_id)
        if not row:
            return False
        self.db.delete(row)
        self.db.commit()
        return True

    # Worker usage
    def list_active_symbols(self) -> list[str]:
        """Get distinct active symbols for price caching"""
        result = (
            self.db.query(TradingBot.symbol)
            .filter(TradingBot.is_active == 1)
            .distinct()
            .all()
        )
        return [row[0] for row in result]

    def list_active_ids(self) -> list[int]:
        """Get all active bot IDs (for worker restart)"""
        result = (
            self.db.query(TradingBot.id)
            .filter(TradingBot.is_active == 1)
            .all()
        )
        return [row[0] for row in result]

    def get_active_by_id(self, bot_id: int) -> TradingBot | None:
        """Get an active bot by id (no user filter, for worker usage)"""
        return (
            self.db.query(TradingBot)
            .filter(TradingBot.id == bot_id, TradingBot.is_active == 1)
            .first()
        )

    def get_user_for_bot(self, bot_id: int) -> User | None:
        """Get the user who owns a bot"""
        row = self.db.query(TradingBot).filter(TradingBot.id == bot_id).first()
        if not row:
            return None
        return self.db.query(User).filter(User.id == row.user_id).first()
