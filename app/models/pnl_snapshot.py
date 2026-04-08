from sqlalchemy import Integer, Float, DateTime, func, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base


class PnlSnapshot(Base):
    __tablename__ = "pnl_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    trading_bot_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("trading_bots.id"), nullable=True, index=True)
    realized_pnl: Mapped[float] = mapped_column(Float, nullable=False)
    unrealized_pnl: Mapped[float] = mapped_column(Float, nullable=False)
    total_pnl: Mapped[float] = mapped_column(Float, nullable=False)
    snapshot_at: Mapped[str] = mapped_column(DateTime, nullable=False, index=True)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())


Index("ix_pnl_snapshots_user_time", PnlSnapshot.user_id, PnlSnapshot.snapshot_at)
Index("ix_pnl_snapshots_bot_time", PnlSnapshot.trading_bot_id, PnlSnapshot.snapshot_at, unique=True)
