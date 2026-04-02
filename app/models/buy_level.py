from sqlalchemy import Integer, Float, String, DateTime, func, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base


class BuyLevel(Base):
    __tablename__ = "buy_levels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trading_bot_id: Mapped[int] = mapped_column(Integer, ForeignKey("trading_bots.id"), index=True)
    level_index: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=max_price .. grid_levels=min_price
    price: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="pending")  # pending | bought | sold
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[str] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


Index("ix_buy_levels_bot_level", BuyLevel.trading_bot_id, BuyLevel.level_index, unique=True)
