from sqlalchemy import String, Integer, Float, DateTime, func, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base


class LstmBot(Base):
    __tablename__ = "lstm_bots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)

    symbol: Mapped[str] = mapped_column(String(20), index=True)  # e.g., "BTCUSDC"
    is_active: Mapped[int] = mapped_column(Integer, default=0)  # 1=active, 0=inactive
    timeframes: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "15m,1d,1w"

    # Trading parameters
    total_amount: Mapped[float] = mapped_column(Float, nullable=False)  # Total USDC budget
    max_positions: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    buy_slope_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    sell_slope_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    take_profit_pct: Mapped[float] = mapped_column(Float, nullable=False, default=2.0)  # % gain to sell
    stop_loss_pct: Mapped[float] = mapped_column(Float, nullable=False, default=3.0)  # % loss max

    # Model status: pending, ready, training, error
    model_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")

    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[str] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


Index("ix_lstm_bots_active", LstmBot.is_active, LstmBot.user_id)
