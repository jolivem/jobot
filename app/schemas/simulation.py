"""Pydantic schemas for simulation and screening endpoints."""

from pydantic import BaseModel, Field
from datetime import datetime


class SimulationRequest(BaseModel):
    interval: str = Field("1h", description="Kline interval (e.g., 1h, 4h, 1d)")
    limit: int = Field(2000, ge=100, le=11000, description="Number of klines to fetch")
    total_amount: float = Field(1000.0, gt=0, description="Simulated trading budget in USDC")
    train_ratio: float = Field(0.7, ge=0.5, le=0.9, description="Train/test split ratio")
    grid_levels_options: list[int] | None = Field(None, description="Grid levels to test")
    sell_percentage_options: list[float] | None = Field(None, description="Sell percentages to test")


class BacktestMetrics(BaseModel):
    total_pnl: float
    total_pnl_pct: float
    num_trades: int
    num_buys: int
    num_sells: int
    win_rate: float
    max_drawdown: float
    sharpe_ratio: float
    final_open_positions: int
    unrealized_pnl: float
    min_price: float
    max_price: float
    grid_levels: int
    sell_percentage: float
    total_amount: float


class SimulationResponse(BaseModel):
    symbol: str
    best_params: BacktestMetrics
    test_result: BacktestMetrics
    top_results: list[BacktestMetrics]
    train_size: int
    test_size: int
    kline_interval: str
    computed_in_ms: int


class ScreeningRequest(BaseModel):
    interval: str = Field("1h", description="Kline interval")
    limit: int = Field(2000, ge=200, le=5000, description="Number of klines per symbol")
    total_amount: float = Field(1000.0, gt=0, description="Simulated trading budget")


class ScreeningLaunchResponse(BaseModel):
    task_id: str
    message: str


class ScreeningSymbolResult(BaseModel):
    symbol: str
    best_pnl_pct: float
    best_min_price: float
    best_max_price: float
    best_grid_levels: int
    best_sell_percentage: float
    num_trades: int
    win_rate: float
    max_drawdown: float
    sharpe_ratio: float
    test_pnl_pct: float
    test_win_rate: float


class ScreeningStatusResponse(BaseModel):
    task_id: str
    status: str
    progress: int
    total_symbols: int
    processed_symbols: int
    results: list[ScreeningSymbolResult]
    started_at: str | None = None
    completed_at: str | None = None
