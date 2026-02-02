from sqlalchemy import String, Integer, Float, DateTime, func, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class PriceAlert(Base):
    __tablename__ = "price_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)

    symbol: Mapped[str] = mapped_column(String(20), index=True)
    target_price: Mapped[float] = mapped_column(Float)
    direction: Mapped[str] = mapped_column(String(10))  # above | below
    is_active: Mapped[int] = mapped_column(Integer, default=1)

    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())

Index("ix_alert_active_symbol", PriceAlert.is_active, PriceAlert.symbol)
