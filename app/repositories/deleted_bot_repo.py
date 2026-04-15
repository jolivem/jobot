from datetime import datetime
from sqlalchemy.orm import Session
from app.models.deleted_bot import DeletedBot


class DeletedBotRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        user_id: int,
        original_bot_id: int,
        symbol: str,
        min_price: float,
        max_price: float,
        total_amount: float,
        sell_percentage: float,
        grid_levels: int,
        realized_pnl: float,
        total_pnl: float,
        created_at: datetime,
    ) -> DeletedBot:
        row = DeletedBot(
            user_id=user_id,
            original_bot_id=original_bot_id,
            symbol=symbol,
            min_price=min_price,
            max_price=max_price,
            total_amount=total_amount,
            sell_percentage=sell_percentage,
            grid_levels=grid_levels,
            realized_pnl=realized_pnl,
            total_pnl=total_pnl,
            created_at=created_at,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def list_by_user(self, user_id: int) -> list[DeletedBot]:
        return (
            self.db.query(DeletedBot)
            .filter(DeletedBot.user_id == user_id)
            .order_by(DeletedBot.deleted_at.desc())
            .all()
        )
