from datetime import datetime
from sqlalchemy.orm import Session
from app.models.pnl_snapshot import PnlSnapshot


class PnlSnapshotRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        user_id: int,
        trading_bot_id: int,
        realized_pnl: float,
        unrealized_pnl: float,
        total_pnl: float,
        snapshot_at: datetime,
    ) -> PnlSnapshot:
        row = PnlSnapshot(
            user_id=user_id,
            trading_bot_id=trading_bot_id,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            total_pnl=total_pnl,
            snapshot_at=snapshot_at,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def exists(self, trading_bot_id: int, snapshot_at: datetime) -> bool:
        return (
            self.db.query(PnlSnapshot)
            .filter(
                PnlSnapshot.trading_bot_id == trading_bot_id,
                PnlSnapshot.snapshot_at == snapshot_at,
            )
            .first()
            is not None
        )

    def delete_by_bot(self, trading_bot_id: int) -> int:
        """Delete all PnL snapshots for a bot. Returns count of deleted rows."""
        count = (
            self.db.query(PnlSnapshot)
            .filter(PnlSnapshot.trading_bot_id == trading_bot_id)
            .delete()
        )
        self.db.commit()
        return count

    def list_by_user(self, user_id: int, since: datetime | None = None) -> list[PnlSnapshot]:
        query = (
            self.db.query(PnlSnapshot)
            .filter(PnlSnapshot.user_id == user_id)
        )
        if since:
            query = query.filter(PnlSnapshot.snapshot_at >= since)
        return query.order_by(PnlSnapshot.snapshot_at.asc()).all()
