from sqlalchemy.orm import Session
from app.models.trade import Trade


class TradeRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, trading_bot_id: int, trade_type: str, price: float, quantity: float) -> Trade:
        row = Trade(
            trading_bot_id=trading_bot_id,
            trade_type=trade_type,
            price=price,
            quantity=quantity,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def list_by_bot(self, trading_bot_id: int) -> list[Trade]:
        return (
            self.db.query(Trade)
            .filter(Trade.trading_bot_id == trading_bot_id)
            .order_by(Trade.created_at.desc())
            .all()
        )

    def delete_by_bot(self, trading_bot_id: int) -> int:
        """Delete all trades for a bot. Returns count of deleted rows."""
        count = (
            self.db.query(Trade)
            .filter(Trade.trading_bot_id == trading_bot_id)
            .delete()
        )
        self.db.commit()
        return count

    def list_by_bots(self, bot_ids: list[int], limit: int = 200) -> list[Trade]:
        """List recent trades across multiple bots."""
        if not bot_ids:
            return []
        return (
            self.db.query(Trade)
            .filter(Trade.trading_bot_id.in_(bot_ids))
            .order_by(Trade.created_at.desc())
            .limit(limit)
            .all()
        )
