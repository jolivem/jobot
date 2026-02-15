"""Unit tests for the backtest engine."""

import os
os.environ["DB_URL_OVERRIDE"] = "sqlite+pysqlite:///:memory:"
os.environ["APP_ENV"] = "test"
os.environ["JWT_SECRET"] = os.environ.get("JWT_SECRET", "test_secret_change_me")

import pytest
from app.services.backtest_engine import run_backtest


class TestBacktestBasic:
    """Basic backtest behavior tests."""

    def test_no_trades_when_price_outside_range(self):
        """Price always above max_price -> no trades."""
        result = run_backtest(
            symbol="TESTUSDC",
            close_prices=[200.0] * 50,
            min_price=100.0,
            max_price=150.0,
            total_amount=1000.0,
            sell_percentage=2.0,
            grid_levels=10,
        )
        assert result.num_trades == 0
        assert result.total_pnl == 0.0

    def test_first_buy_when_price_in_range(self):
        """Price enters range -> at least one buy."""
        result = run_backtest(
            symbol="TESTUSDC",
            close_prices=[120.0] * 10,
            min_price=100.0,
            max_price=150.0,
            total_amount=1000.0,
            sell_percentage=2.0,
            grid_levels=10,
        )
        assert result.num_buys >= 1
        assert result.final_open_positions >= 1

    def test_buy_and_sell_cycle(self):
        """Price enters range, rises enough -> buy then sell."""
        prices = [
            100.0,   # first buy
            102.5,   # gain > 2%, highest = 102.5
            102.0,   # pullback -> sell
        ]
        result = run_backtest(
            symbol="TESTUSDC",
            close_prices=prices,
            min_price=90.0,
            max_price=200.0,
            total_amount=1000.0,
            sell_percentage=2.0,
            grid_levels=10,
        )
        assert result.num_buys == 1
        assert result.num_sells == 1
        assert result.total_pnl > 0
        assert result.win_rate == 1.0
        assert result.final_open_positions == 0

    def test_grid_buys_on_dip(self):
        """Price drops through grid levels -> multiple buys."""
        prices = [
            150.0,   # first buy
            142.0,   # below 140
            139.0,   # lowest
            139.5,   # bounce
            139.3,   # BUY at grid level
            122.0,   # below 120
            119.0,   # lowest
            119.5,   # bounce
            119.3,   # BUY at grid level
        ]
        result = run_backtest(
            symbol="TESTUSDC",
            close_prices=prices,
            min_price=100.0,
            max_price=200.0,
            total_amount=1000.0,
            sell_percentage=2.0,
            grid_levels=5,
        )
        assert result.num_buys == 3
        assert result.final_open_positions == 3


class TestBacktestMetrics:
    """Tests for metric calculations."""

    def test_pnl_percentage_matches(self):
        """total_pnl_pct should be total_pnl / total_amount * 100."""
        prices = [100.0, 102.5, 102.0, 101.0]
        result = run_backtest(
            symbol="TESTUSDC",
            close_prices=prices,
            min_price=90.0,
            max_price=200.0,
            total_amount=1000.0,
            sell_percentage=2.0,
            grid_levels=10,
        )
        expected_pct = result.total_pnl / 1000.0 * 100
        assert result.total_pnl_pct == pytest.approx(expected_pct, abs=0.01)

    def test_max_drawdown_on_dip(self):
        """Drawdown should be positive when price drops after buy."""
        prices = [
            100.0,  # buy
            80.0,   # significant drop
            80.0,
        ]
        result = run_backtest(
            symbol="TESTUSDC",
            close_prices=prices,
            min_price=50.0,
            max_price=200.0,
            total_amount=1000.0,
            sell_percentage=5.0,
            grid_levels=10,
        )
        assert result.max_drawdown > 0

    def test_parameters_stored_in_result(self):
        """BacktestResult should store the parameters used."""
        result = run_backtest(
            symbol="TESTUSDC",
            close_prices=[150.0] * 5,
            min_price=100.0,
            max_price=200.0,
            total_amount=500.0,
            sell_percentage=3.0,
            grid_levels=7,
        )
        assert result.min_price == 100.0
        assert result.max_price == 200.0
        assert result.total_amount == 500.0
        assert result.sell_percentage == 3.0
        assert result.grid_levels == 7

    def test_empty_prices(self):
        """Empty price list -> no trades, zero P&L."""
        result = run_backtest(
            symbol="TESTUSDC",
            close_prices=[],
            min_price=100.0,
            max_price=200.0,
            total_amount=1000.0,
            sell_percentage=2.0,
            grid_levels=10,
        )
        assert result.num_trades == 0
        assert result.total_pnl == 0.0


class TestBacktestFullScenario:
    """End-to-end backtest scenarios."""

    def test_full_grid_cycle(self):
        """Complete cycle: buy at multiple levels, sell all, positive P&L."""
        prices = [
            150.0,   # BUY #1
            142.0,
            139.0,
            139.5,
            139.3,   # BUY #2
            122.0,
            119.0,
            119.5,
            119.3,   # BUY #3
            # Recovery
            124.0,
            123.5,
            123.0,   # SELL #3 (3.5% gain from 119.3)
            143.0,
            145.0,
            144.5,   # SELL #2 (4.1% gain from 139.3)
            155.0,
            154.5,   # SELL #1 (3.3% gain from 150)
        ]
        result = run_backtest(
            symbol="TESTUSDC",
            close_prices=prices,
            min_price=100.0,
            max_price=200.0,
            total_amount=1000.0,
            sell_percentage=3.0,
            grid_levels=5,
        )
        assert result.num_buys == 3
        assert result.num_sells == 3
        assert result.total_pnl > 0
        assert result.win_rate == 1.0
        assert result.final_open_positions == 0

    def test_restart_cycle(self):
        """After selling all, bot should restart buying."""
        prices = [
            100.0,   # buy
            102.5,   # gain
            102.0,   # sell
            101.0,   # restart buy
        ]
        result = run_backtest(
            symbol="TESTUSDC",
            close_prices=prices,
            min_price=90.0,
            max_price=200.0,
            total_amount=1000.0,
            sell_percentage=2.0,
            grid_levels=10,
        )
        assert result.num_buys == 2
        assert result.num_sells == 1
