"""Unit tests for the grid trading strategy.

Tests use a fake bot object and simulate price sequences tick by tick
to verify buy/sell decisions match the expected grid behavior.
"""

import os
os.environ["DB_URL_OVERRIDE"] = "sqlite+pysqlite:///:memory:"
os.environ["APP_ENV"] = "test"
os.environ["JWT_SECRET"] = os.environ.get("JWT_SECRET", "test_secret_change_me")

import pytest
from types import SimpleNamespace
from app.services.trading_strategy import decide_trade


def make_bot(**overrides):
    """Create a fake bot object with default grid parameters."""
    defaults = {
        "id": 1,
        "symbol": "SOLUSDC",
        "max_price": 200.0,
        "min_price": 100.0,
        "total_amount": 10.0,      # 10 USDC per order
        "buy_percentage": 2.0,      # buy when price drops 2% from lowest entry
        "sell_percentage": 2.0,     # sell when price rises 2% from entry
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def run_prices(bot, prices):
    """Run a sequence of prices through the strategy and return all decisions."""
    state = {"positions": [], "lowest_price": None}
    previous_price = None
    all_decisions = []
    for price in prices:
        decisions, state = decide_trade(bot, price, state, previous_price)
        for d in decisions:
            all_decisions.append({**d, "price_at_tick": price})
        previous_price = price
    return all_decisions, state


class TestFirstBuy:
    """Tests for the initial buy behavior."""

    def test_first_tick_buys_when_below_max_price(self):
        bot = make_bot(max_price=200.0)
        state = {"positions": [], "lowest_price": None}
        decisions, state = decide_trade(bot, 150.0, state, None)
        assert len(decisions) == 1
        assert decisions[0]["side"] == "buy"
        assert decisions[0]["entry_price"] == 150.0
        assert len(state["positions"]) == 1

    def test_first_tick_no_buy_when_above_max_price(self):
        bot = make_bot(max_price=100.0)
        state = {"positions": [], "lowest_price": None}
        decisions, state = decide_trade(bot, 150.0, state, None)
        assert len(decisions) == 0
        assert len(state["positions"]) == 0

    def test_quantity_is_total_amount_divided_by_price(self):
        bot = make_bot(total_amount=10.0)
        state = {"positions": [], "lowest_price": None}
        decisions, _ = decide_trade(bot, 100.0, state, None)
        assert decisions[0]["quantity"] == pytest.approx(0.1, rel=1e-6)


class TestGridBuy:
    """Tests for grid buy (buying on dips with pullback confirmation)."""

    def test_no_second_buy_without_sufficient_drop(self):
        """Price drops only 1% from entry (need 2%), no second buy."""
        bot = make_bot(buy_percentage=2.0)
        prices = [100.0, 99.5, 99.0]  # 1% drop only
        decisions, state = run_prices(bot, prices)
        buys = [d for d in decisions if d["side"] == "buy"]
        assert len(buys) == 1  # only the first buy

    def test_second_buy_on_sufficient_drop_with_pullback(self):
        """Price drops 2%+ from entry, then small pullback -> second buy."""
        bot = make_bot(buy_percentage=2.0, max_price=200.0)
        # First buy at 100, then drop to 97 (3% drop), tiny bounce to 97.2, then back down
        prices = [
            100.0,   # first buy
            99.0,    # dropping
            97.0,    # 3% below entry, lowest_price set
            97.3,    # bounce up (above 97 * 1.002 = 97.194), but price > previous
            97.2,    # price < previous (97.3) and >= pullback_price -> BUY
        ]
        decisions, state = run_prices(bot, prices)
        buys = [d for d in decisions if d["side"] == "buy"]
        assert len(buys) == 2
        assert buys[1]["entry_price"] == 97.2

    def test_grid_buy_respects_max_price(self):
        """Grid buy works below max_price, but not above."""
        # Case 1: grid buy happens when price is below max_price
        bot = make_bot(buy_percentage=2.0, max_price=95.0)
        prices = [
            90.0,    # first buy (below max_price=95)
            88.0,    # drop
            87.0,    # 3% below 90, lowest_price=87.0
            87.5,    # bounce: 87.5 >= 87.0*1.002=87.174
            87.3,    # price < previous (87.5) and >= pullback -> BUY
        ]
        decisions, state = run_prices(bot, prices)
        buys = [d for d in decisions if d["side"] == "buy"]
        assert len(buys) == 2

        # Case 2: no grid buy when initial price is above max_price
        bot2 = make_bot(buy_percentage=2.0, max_price=85.0)
        state2 = {"positions": [], "lowest_price": None}
        decisions2, _ = decide_trade(bot2, 90.0, state2, None)
        assert len(decisions2) == 0  # price > max_price, no buy


class TestSell:
    """Tests for sell behavior with pullback confirmation."""

    def test_sell_on_sufficient_gain_with_pullback(self):
        """Price rises 2%+ from entry, then pulls back -> sell."""
        bot = make_bot(sell_percentage=2.0)
        prices = [
            100.0,   # first buy at 100
            101.0,   # rising
            102.5,   # 2.5% gain, highest set to 102.5
            102.0,   # pullback: 102.0 <= 102.5 * (1 - 0.002) = 102.295 -> SELL
        ]
        decisions, state = run_prices(bot, prices)
        sells = [d for d in decisions if d["side"] == "sell"]
        assert len(sells) == 1
        assert sells[0]["entry_price"] == 102.0

    def test_no_sell_without_pullback(self):
        """Price keeps rising without pullback, no sell triggered."""
        bot = make_bot(sell_percentage=2.0)
        prices = [100.0, 101.0, 102.0, 102.5, 103.0, 103.5]
        decisions, state = run_prices(bot, prices)
        sells = [d for d in decisions if d["side"] == "sell"]
        assert len(sells) == 0

    def test_no_sell_without_sufficient_gain(self):
        """Price rises only 1% (need 2%), no sell even with pullback."""
        bot = make_bot(sell_percentage=2.0)
        prices = [100.0, 101.0, 100.8]  # 1% gain, then pullback
        decisions, state = run_prices(bot, prices)
        sells = [d for d in decisions if d["side"] == "sell"]
        assert len(sells) == 0


class TestCycleRestart:
    """Tests for cycle restart after all positions are sold."""

    def test_restart_buy_after_all_sold(self):
        """After all positions sold, bot should buy again if price <= max_price."""
        bot = make_bot(sell_percentage=2.0, max_price=200.0)
        prices = [
            100.0,   # first buy
            102.5,   # gain > 2%, highest = 102.5
            102.0,   # pullback -> sell
            101.0,   # no positions, price <= max_price -> new buy (restart)
        ]
        decisions, state = run_prices(bot, prices)
        buys = [d for d in decisions if d["side"] == "buy"]
        sells = [d for d in decisions if d["side"] == "sell"]
        assert len(buys) == 2  # first buy + restart buy
        assert len(sells) == 1

    def test_no_restart_buy_above_max_price(self):
        """After all sold, no new buy if price > max_price."""
        bot = make_bot(sell_percentage=2.0, max_price=100.0)
        prices = [
            99.0,    # first buy (below max_price)
            101.5,   # gain > 2%, highest
            101.0,   # pullback -> sell
            101.0,   # no positions, but price > max_price -> no buy
        ]
        decisions, state = run_prices(bot, prices)
        buys = [d for d in decisions if d["side"] == "buy"]
        assert len(buys) == 1  # only first buy, no restart


class TestMultiplePositions:
    """Tests for managing multiple grid positions simultaneously."""

    def test_independent_sell_per_position(self):
        """Each position sells independently based on its own entry price."""
        bot = make_bot(buy_percentage=2.0, sell_percentage=2.0, max_price=200.0)
        prices = [
            100.0,   # BUY #1 at 100
            97.5,    # drop 2.5%
            97.0,    # lowest
            97.3,    # bounce
            97.2,    # BUY #2 at 97.2 (pullback confirmed)
            99.5,    # rising - 2.3% gain on pos2 (entry 97.2), highest=99.5
            99.0,    # pullback from 99.5: 99.0 <= 99.5*0.998=99.301 -> SELL pos2
            # pos1 still open (only 99/100 = -1% loss, not enough gain)
            102.5,   # 2.5% gain on pos1 (entry 100), highest=102.5
            102.0,   # pullback -> SELL pos1
        ]
        decisions, state = run_prices(bot, prices)
        buys = [d for d in decisions if d["side"] == "buy"]
        sells = [d for d in decisions if d["side"] == "sell"]
        assert len(buys) == 2
        assert len(sells) == 2
        # After all sold, state should have no positions
        assert len(state["positions"]) == 0

    def test_lowest_price_reset_after_buy(self):
        """lowest_price should reset to None after each buy."""
        bot = make_bot(buy_percentage=2.0)
        state = {"positions": [], "lowest_price": None}

        # First buy
        _, state = decide_trade(bot, 100.0, state, None)
        assert state["lowest_price"] is None

        # Price drops, lowest_price tracks
        _, state = decide_trade(bot, 98.0, state, 100.0)
        assert state["lowest_price"] == 98.0

        _, state = decide_trade(bot, 97.0, state, 98.0)
        assert state["lowest_price"] == 97.0


class TestFullScenario:
    """End-to-end scenario simulating a realistic price sequence."""

    def test_full_grid_cycle(self):
        """Simulate a full grid cycle: buy -> grid buys on dips -> sell on recovery."""
        bot = make_bot(
            buy_percentage=3.0,
            sell_percentage=3.0,
            total_amount=10.0,
            max_price=110.0,
        )
        # Simulate: price starts at 100, drops to ~93, then recovers to ~103
        prices = [
            100.0,   # BUY (first buy, no positions)
            98.0,    # tracking lowest
            96.5,    # 3.5% drop from 100
            96.0,    # new lowest
            96.3,    # bounce: 96.3 >= 96.0*1.002=96.192, and 96.3 < 96.5? no, 96.3 < 96.5
            96.2,    # 96.2 < 96.3 (previous) and >= 96.0*1.002=96.192 -> BUY #2
            95.0,    # more drop
            93.0,    # 3.3% drop from 96.2 (lowest entry)
            92.5,    # lowest
            92.8,    # bounce
            92.7,    # BUY #3: 92.7 < 92.8 and >= 92.5*1.002=92.685 -> buy
            94.0,    # recovery
            96.0,
            98.0,
            99.5,    # 99.5 / 92.7 = 1.073 -> 7.3% gain on pos3 (entry 92.7)
            99.0,    # pullback -> SELL pos3
            100.0,
            99.5,    # 99.5/96.2 = 1.034 -> 3.4% gain on pos2, highest tracking
            99.2,    # pullback from 99.5 -> SELL pos2
            102.0,
            103.5,   # 103.5/100 = 3.5% gain on pos1
            103.0,   # pullback -> SELL pos1
        ]
        decisions, state = run_prices(bot, prices)
        buys = [d for d in decisions if d["side"] == "buy"]
        sells = [d for d in decisions if d["side"] == "sell"]

        assert len(buys) == 3
        assert len(sells) == 3
        assert len(state["positions"]) == 0  # all sold

    def test_no_activity_when_price_flat(self):
        """If price stays flat, only the initial buy happens."""
        bot = make_bot()
        prices = [100.0] * 20
        decisions, state = run_prices(bot, prices)
        buys = [d for d in decisions if d["side"] == "buy"]
        assert len(buys) == 1  # only initial buy
        assert len(state["positions"]) == 1
