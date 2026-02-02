from sqlalchemy import String, Integer, Float, DateTime, func, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class PortfolioAsset(Base):
    __tablename__ = "portfolio_assets"
    __table_args__ = (
        UniqueConstraint("user_id", "symbol", name="uq_user_symbol"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)

    symbol: Mapped[str] = mapped_column(String(20), index=True)  # e.g. BTCUSDT
    quantity: Mapped[float] = mapped_column(Float, default=0.0)

    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[str] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
