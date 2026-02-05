from sqlalchemy import String, Integer, Float, DateTime, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trading_bot_id: Mapped[int] = mapped_column(Integer, ForeignKey("trading_bots.id"), index=True)
    trade_type: Mapped[str] = mapped_column(String(10), nullable=False)  # 'buy' | 'sell'
    price: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now(), index=True)
