from sqlalchemy import String, Integer, Float, DateTime, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base


class ScreeningResult(Base):
    __tablename__ = "screening_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)

    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    best_pnl_pct: Mapped[float] = mapped_column(Float, nullable=False)
    best_min_price: Mapped[float] = mapped_column(Float, nullable=False)
    best_max_price: Mapped[float] = mapped_column(Float, nullable=False)
    best_grid_levels: Mapped[int] = mapped_column(Integer, nullable=False)
    best_sell_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    num_trades: Mapped[int] = mapped_column(Integer, nullable=False)
    win_rate: Mapped[float] = mapped_column(Float, nullable=False)
    max_drawdown: Mapped[float] = mapped_column(Float, nullable=False)
    sharpe_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    test_pnl_pct: Mapped[float] = mapped_column(Float, nullable=False)
    test_win_rate: Mapped[float] = mapped_column(Float, nullable=False)

    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())
