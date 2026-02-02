from sqlalchemy import String, Integer, Float, DateTime, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class AlertEvent(Base):
    __tablename__ = "alert_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_id: Mapped[int] = mapped_column(Integer, ForeignKey("price_alerts.id"), index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)

    symbol: Mapped[str] = mapped_column(String(20), index=True)
    triggered_price: Mapped[float] = mapped_column(Float)

    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())
