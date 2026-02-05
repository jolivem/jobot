from sqlalchemy import String, Integer, Float, DateTime, func, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base


class TradingBot(Base):
    __tablename__ = "trading_bots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)

    symbol: Mapped[str] = mapped_column(String(20), index=True)  # e.g., "BTCUSDT"
    is_active: Mapped[int] = mapped_column(Integer, default=1)  # 1=active, 0=inactive

    # Trading parameters
    max_price: Mapped[float] = mapped_column(Float, nullable=False)  # Maximum price threshold
    min_price: Mapped[float] = mapped_column(Float, nullable=False)  # Minimum price threshold
    total_amount: Mapped[float] = mapped_column(Float, nullable=False)  # Total amount to trade
    sell_percentage: Mapped[float] = mapped_column(Float, nullable=False)  # % increase before selling
    buy_percentage: Mapped[float] = mapped_column(Float, nullable=False)  # % decrease before buying

    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[str] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


# Composite index for efficient queries: active bots by user
Index("ix_trading_bots_active", TradingBot.is_active, TradingBot.user_id)
