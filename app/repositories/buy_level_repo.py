from sqlalchemy.orm import Session
from app.models.buy_level import BuyLevel


class BuyLevelRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_grid(self, trading_bot_id: int, max_price: float, min_price: float, grid_levels: int) -> list[BuyLevel]:
        """Create all buy levels for a bot (0=max .. grid_levels=min)."""
        step = (max_price - min_price) / grid_levels
        levels = []
        for i in range(grid_levels + 1):
            level = BuyLevel(
                trading_bot_id=trading_bot_id,
                level_index=i,
                price=round(max_price - i * step, 8),
                status="pending",
            )
            self.db.add(level)
            levels.append(level)
        self.db.commit()
        return levels

    def list_by_bot(self, trading_bot_id: int) -> list[BuyLevel]:
        return (
            self.db.query(BuyLevel)
            .filter(BuyLevel.trading_bot_id == trading_bot_id)
            .order_by(BuyLevel.level_index)
            .all()
        )

    def update_status(self, trading_bot_id: int, level_index: int, status: str):
        self.db.query(BuyLevel).filter(
            BuyLevel.trading_bot_id == trading_bot_id,
            BuyLevel.level_index == level_index,
        ).update({"status": status})
        self.db.commit()

    def reset_all(self, trading_bot_id: int):
        """Reset all levels to pending (new cycle)."""
        self.db.query(BuyLevel).filter(
            BuyLevel.trading_bot_id == trading_bot_id,
        ).update({"status": "pending"})
        self.db.commit()

    def delete_by_bot(self, trading_bot_id: int):
        self.db.query(BuyLevel).filter(
            BuyLevel.trading_bot_id == trading_bot_id,
        ).delete()
        self.db.commit()
