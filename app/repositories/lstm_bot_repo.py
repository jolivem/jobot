from sqlalchemy.orm import Session
from app.models.lstm_bot import LstmBot
from app.models.user import User


class LstmBotRepository:
    def __init__(self, db: Session):
        self.db = db

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
    ) -> LstmBot:
        row = LstmBot(
            user_id=user_id,
            symbol=symbol.upper().strip(),
            timeframes=timeframes,
            total_amount=total_amount,
            max_positions=max_positions,
            buy_slope_threshold=buy_slope_threshold,
            sell_slope_threshold=sell_slope_threshold,
            take_profit_pct=take_profit_pct,
            stop_loss_pct=stop_loss_pct,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def update(self, user_id: int, bot_id: int, **kwargs) -> LstmBot | None:
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

    def list_by_user(self, user_id: int) -> list[LstmBot]:
        return (
            self.db.query(LstmBot)
            .filter(LstmBot.user_id == user_id)
            .order_by(LstmBot.id.desc())
            .all()
        )

    def get_by_id(self, user_id: int, bot_id: int) -> LstmBot | None:
        return (
            self.db.query(LstmBot)
            .filter(LstmBot.user_id == user_id, LstmBot.id == bot_id)
            .first()
        )

    def deactivate(self, user_id: int, bot_id: int) -> LstmBot | None:
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

    def set_model_status(self, bot_id: int, status: str):
        row = self.db.query(LstmBot).filter(LstmBot.id == bot_id).first()
        if row:
            row.model_status = status
            self.db.commit()

    # Worker usage
    def list_active_ids(self) -> list[int]:
        result = (
            self.db.query(LstmBot.id)
            .filter(LstmBot.is_active == 1)
            .all()
        )
        return [row[0] for row in result]

    def list_active_symbols(self) -> list[str]:
        result = (
            self.db.query(LstmBot.symbol)
            .filter(LstmBot.is_active == 1)
            .distinct()
            .all()
        )
        return [row[0] for row in result]

    def get_active_by_id(self, bot_id: int) -> LstmBot | None:
        return (
            self.db.query(LstmBot)
            .filter(LstmBot.id == bot_id, LstmBot.is_active == 1)
            .first()
        )

    def get_user_for_bot(self, bot_id: int) -> User | None:
        row = self.db.query(LstmBot).filter(LstmBot.id == bot_id).first()
        if not row:
            return None
        return self.db.query(User).filter(User.id == row.user_id).first()
