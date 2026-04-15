from sqlalchemy import String, Integer, Float, DateTime, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base


class DeletedBot(Base):
    __tablename__ = "deleted_bots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    original_bot_id: Mapped[int] = mapped_column(Integer)

    symbol: Mapped[str] = mapped_column(String(20))
    min_price: Mapped[float] = mapped_column(Float, nullable=False)
    max_price: Mapped[float] = mapped_column(Float, nullable=False)
    total_amount: Mapped[float] = mapped_column(Float, nullable=False)
    sell_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    grid_levels: Mapped[int] = mapped_column(Integer, nullable=False)

    realized_pnl: Mapped[float] = mapped_column(Float, nullable=False)
    total_pnl: Mapped[float] = mapped_column(Float, nullable=False)

    created_at: Mapped[str] = mapped_column(DateTime, nullable=False)
    deleted_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())
