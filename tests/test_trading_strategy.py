"""Unit tests for the fixed-price grid trading strategy.

Tests use a fake bot object and simulate price sequences tick by tick
to verify buy/sell decisions match the expected grid behavior.
"""

import os
os.environ["DB_URL_OVERRIDE"] = "sqlite+pysqlite:///:memory:"
os.environ["APP_ENV"] = "test"
os.environ["JWT_SECRET"] = os.environ.get("JWT_SECRET", "test_secret_change_me")

import pytest
from types import SimpleNamespace
from app.services.trading_strategy import decide_trade, reconstruct_state_from_trades, _create_buy_levels_from_config


def make_bot(**overrides):
    """Create a fake bot object with default grid parameters."""
    defaults = {
        "id": 1,
        "symbol": "SOLUSDC",
        "max_price": 200.0,
        "min_price": 100.0,
        "total_amount": 1000.0,    # 1000 USDC total budget
        "grid_levels": 10,         # 10 buy levels
        "sell_percentage": 2.0,    # sell when price rises 2% from entry
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def empty_state(bot=None):
    if bot is None:
        bot = make_bot()
    return {
        "positions": [],
        "lowest_price": None,
        "buy_levels": _create_buy_levels_from_config(bot),
    }


def run_prices(bot, prices):
    """Run a sequence of prices through the strategy and return all decisions."""
    state = empty_state(bot)
    previous_price = None
    all_decisions = []
    for price in prices:
        decisions, state = decide_trade(bot, price, state, previous_price)
        for d in decisions:
            all_decisions.append({**d, "price_at_tick": price})
        previous_price = price
    return all_decisions, state


class TestBuyLevels:
    """Tests for buy_levels creation."""

    def test_basic_levels(self):
        """10 grid_levels -> 11 levels from max to min."""
        bot = make_bot(max_price=150.0, min_price=100.0, grid_levels=10)
        levels = _create_buy_levels_from_config(bot)
        assert len(levels) == 11
        assert levels[0]["price"] == pytest.approx(150.0)
        assert levels[10]["price"] == pytest.approx(100.0)
        # step = 5
        assert levels[1]["price"] == pytest.approx(145.0)
        assert levels[9]["price"] == pytest.approx(105.0)
        assert all(lvl["status"] == "pending" for lvl in levels)

    def test_two_levels(self):
        bot = make_bot(max_price=150.0, min_price=100.0, grid_levels=2)
        levels = _create_buy_levels_from_config(bot)
        assert len(levels) == 3
        assert levels[0]["price"] == pytest.approx(150.0)
        assert levels[1]["price"] == pytest.approx(125.0)
        assert levels[2]["price"] == pytest.approx(100.0)

    def test_one_level(self):
        bot = make_bot(max_price=150.0, min_price=100.0, grid_levels=1)
        levels = _create_buy_levels_from_config(bot)
        assert len(levels) == 2
        assert levels[0]["price"] == pytest.approx(150.0)
        assert levels[1]["price"] == pytest.approx(100.0)


class TestFirstBuy:
    """Tests for the initial buy behavior."""

    def test_first_tick_buys_when_between_min_and_max_price(self):
        bot = make_bot(max_price=200.0, min_price=100.0, grid_levels=10)
        state = empty_state(bot)
        decisions, state = decide_trade(bot, 150.0, state, None)
        assert len(decisions) == 1
        assert decisions[0]["side"] == "buy"
        assert decisions[0]["entry_price"] == 150.0
        assert len(state["positions"]) == 1
        assert len(state["buy_levels"]) == 11

    def test_first_tick_no_buy_when_above_max_price(self):
        bot = make_bot(max_price=100.0, min_price=50.0)
        state = empty_state(bot)
        decisions, state = decide_trade(bot, 150.0, state, None)
        assert len(decisions) == 0
        assert len(state["positions"]) == 0

    def test_first_tick_no_buy_when_below_min_price(self):
        bot = make_bot(max_price=200.0, min_price=100.0)
        state = empty_state(bot)
        decisions, state = decide_trade(bot, 90.0, state, None)
        assert len(decisions) == 0
        assert len(state["positions"]) == 0

    def test_quantity_is_total_amount_divided_by_grid_levels_and_price(self):
        bot = make_bot(total_amount=1000.0, grid_levels=10)
        state = empty_state(bot)
        decisions, _ = decide_trade(bot, 100.0, state, None)
        # qty = 1000 / 10 / 100 = 1.0
        assert decisions[0]["quantity"] == pytest.approx(1.0, rel=1e-6)


class TestGridBuy:
    """Tests for grid buy at fixed price levels with pullback confirmation."""

    def test_buy_at_first_grid_level_with_pullback(self):
        """First buy at 150, deepest available level below 150 with pullback -> buy."""
        bot = make_bot(max_price=200.0, min_price=100.0, grid_levels=10)
        # Levels: [200, 190, 180, 170, 160, 150, 140, 130, 120, 110, 100]
        # Level 6 = 140 is the deepest where price drops to
        prices = [
            150.0,   # first buy
            142.0,   # tracking
            140.0,   # at level 6 (140)
            139.0,   # below, lowest_price = 139
            139.4,   # bounce: 139.4 >= 139.0 * 1.002 = 139.278
            139.3,   # 139.3 < 139.4 (prev) and >= pullback -> BUY
        ]
        decisions, state = run_prices(bot, prices)
        buys = [d for d in decisions if d["side"] == "buy"]
        assert len(buys) == 2
        assert buys[1]["entry_price"] == 139.3
        assert buys[1]["grid_level"] == 6  # level for price 140

    def test_no_buy_without_pullback(self):
        """Price drops to grid level but keeps falling, no pullback -> no buy."""
        bot = make_bot(max_price=200.0, min_price=100.0, grid_levels=10)
        prices = [
            150.0,   # first buy
            142.0,
            140.0,
            139.0,   # keeps dropping
            138.0,
            137.0,
        ]
        decisions, state = run_prices(bot, prices)
        buys = [d for d in decisions if d["side"] == "buy"]
        assert len(buys) == 1  # only first buy

    def test_no_buy_above_grid_level(self):
        """Price stays above first grid level, no second buy."""
        bot = make_bot(min_price=100.0, grid_levels=10)
        prices = [150.0, 148.0, 147.0, 146.0, 147.0, 146.5]
        decisions, state = run_prices(bot, prices)
        buys = [d for d in decisions if d["side"] == "buy"]
        assert len(buys) == 1  # only first buy

    def test_multiple_grid_buys(self):
        """Buy at multiple grid levels sequentially."""
        bot = make_bot(max_price=200.0, min_price=100.0, grid_levels=5)
        # Levels: [200, 180, 160, 140, 120, 100], step=20
        prices = [
            150.0,   # first buy
            142.0,   # below 140 (level 3)
            139.0,   # lowest
            139.5,   # bounce
            139.3,   # BUY at level 3 (140)
            122.0,   # below 120 (level 4)
            119.0,   # lowest
            119.5,   # bounce
            119.3,   # BUY at level 4 (120)
        ]
        decisions, state = run_prices(bot, prices)
        buys = [d for d in decisions if d["side"] == "buy"]
        assert len(buys) == 3

    def test_grid_buy_respects_max_price(self):
        """No grid buy when price > max_price."""
        bot = make_bot(max_price=145.0, min_price=100.0, grid_levels=5)
        # Levels: [145, 136, 127, 118, 109, 100], step=9
        prices = [
            140.0,   # first buy
            137.0,
            135.0,   # below 136 (level 1)
            135.5,   # bounce
            135.3,   # BUY
        ]
        decisions, state = run_prices(bot, prices)
        buys = [d for d in decisions if d["side"] == "buy"]
        assert len(buys) == 2


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
        assert sells[0]["buy_entry"] == 100.0

    def test_sell_decision_contains_buy_entry(self):
        bot = make_bot(sell_percentage=2.0)
        prices = [
            100.0,   # BUY at 100
            102.5,   # 2.5% gain, highest=102.5
            102.0,   # pullback -> SELL
        ]
        decisions, state = run_prices(bot, prices)
        sells = [d for d in decisions if d["side"] == "sell"]
        assert len(sells) == 1
        assert sells[0]["buy_entry"] == 100.0
        assert sells[0]["entry_price"] == 102.0

    def test_no_sell_without_pullback(self):
        bot = make_bot(sell_percentage=2.0)
        prices = [100.0, 101.0, 102.0, 102.5, 103.0, 103.5]
        decisions, state = run_prices(bot, prices)
        sells = [d for d in decisions if d["side"] == "sell"]
        assert len(sells) == 0

    def test_no_sell_without_sufficient_gain(self):
        bot = make_bot(sell_percentage=2.0)
        prices = [100.0, 101.0, 100.8]
        decisions, state = run_prices(bot, prices)
        sells = [d for d in decisions if d["side"] == "sell"]
        assert len(sells) == 0


class TestCycleRestart:
    """Tests for cycle restart after all positions are sold."""

    def test_restart_buy_after_all_sold(self):
        bot = make_bot(sell_percentage=2.0, max_price=200.0)
        prices = [
            100.0,   # first buy
            102.5,   # gain > 2%, highest = 102.5
            102.0,   # pullback -> sell
            101.0,   # no positions -> new buy (restart)
        ]
        decisions, state = run_prices(bot, prices)
        buys = [d for d in decisions if d["side"] == "buy"]
        sells = [d for d in decisions if d["side"] == "sell"]
        assert len(buys) == 2
        assert len(sells) == 1
        # All levels should be reset to pending after cycle restart
        assert all(lvl["status"] == "pending" for lvl in state["buy_levels"]
                   if lvl["level_index"] != -1)

    def test_no_restart_buy_above_max_price(self):
        bot = make_bot(sell_percentage=2.0, max_price=100.0, min_price=90.0)
        prices = [
            99.0,    # first buy
            101.5,   # gain > 2%, highest
            101.0,   # pullback -> sell
            101.0,   # no positions, but price > max_price -> no buy
        ]
        decisions, state = run_prices(bot, prices)
        buys = [d for d in decisions if d["side"] == "buy"]
        assert len(buys) == 1


class TestMultiplePositions:
    """Tests for managing multiple grid positions simultaneously."""

    def test_independent_sell_per_position(self):
        bot = make_bot(grid_levels=5, sell_percentage=2.0, max_price=200.0, min_price=100.0)
        # Levels: [200, 180, 160, 140, 120, 100]
        prices = [
            150.0,   # BUY #1 at 150
            142.0,   # below 140 (level 3)
            139.0,   # lowest
            139.5,   # bounce
            139.3,   # BUY #2 at level 3 (140)
            142.5,   # 142.5/139.3 = 2.3% on pos2, highest=142.5
            142.0,   # pullback -> SELL pos2
            153.5,   # 153.5/150 = 2.3% gain on pos1, highest=153.5
            153.0,   # pullback -> SELL pos1
        ]
        decisions, state = run_prices(bot, prices)
        buys = [d for d in decisions if d["side"] == "buy"]
        sells = [d for d in decisions if d["side"] == "sell"]
        assert len(buys) == 2
        assert len(sells) == 2
        assert len(state["positions"]) == 0
        sell_buy_entries = sorted([s["buy_entry"] for s in sells])
        assert sell_buy_entries == pytest.approx([139.3, 150.0])

    def test_no_duplicate_buy_at_same_level(self):
        bot = make_bot(max_price=200.0, min_price=100.0, grid_levels=10)
        # Levels: [200,190,180,...,110,100], level 6 = 140
        state = empty_state(bot)

        # First buy at 150
        decisions, state = decide_trade(bot, 150.0, state, None)
        assert len(decisions) == 1

        # Drop to level 6 (140), bounce, buy
        _, state = decide_trade(bot, 139.0, state, 150.0)
        _, state = decide_trade(bot, 139.5, state, 139.0)
        decisions, state = decide_trade(bot, 139.3, state, 139.5)
        assert len(decisions) == 1
        assert decisions[0]["grid_level"] == 6

        # Price comes back to same level -> no buy (level 6 is occupied)
        _, state = decide_trade(bot, 140.0, state, 139.3)
        _, state = decide_trade(bot, 139.0, state, 140.0)
        decisions, state = decide_trade(bot, 139.3, state, 139.5)
        assert len(decisions) == 0

    def test_lowest_price_reset_after_first_buy(self):
        bot = make_bot()
        state = empty_state(bot)

        _, state = decide_trade(bot, 150.0, state, None)
        assert state["lowest_price"] == 150.0

        _, state = decide_trade(bot, 148.0, state, 150.0)
        assert state["lowest_price"] == 148.0

        _, state = decide_trade(bot, 147.0, state, 148.0)
        assert state["lowest_price"] == 147.0


class TestReconstructState:
    """Tests for reconstruct_state_from_trades."""

    def test_empty_trades(self):
        bot = make_bot()
        state = reconstruct_state_from_trades(bot, [])
        assert state["positions"] == []
        assert state["lowest_price"] is None
        assert len(state["buy_levels"]) == 11

    def test_all_sold(self):
        bot = make_bot()
        trades = [
            SimpleNamespace(trade_type="buy", price=150.0, quantity=0.667, created_at=1, grid_level=-1),
            SimpleNamespace(trade_type="sell", price=153.0, quantity=0.667, created_at=2, grid_level=-1),
        ]
        state = reconstruct_state_from_trades(bot, trades)
        assert state["positions"] == []

    def test_open_positions(self):
        bot = make_bot(max_price=200.0, min_price=100.0, grid_levels=10)
        trades = [
            SimpleNamespace(trade_type="buy", price=150.0, quantity=0.667, created_at=1, grid_level=-1),
            SimpleNamespace(trade_type="buy", price=140.0, quantity=0.714, created_at=2, grid_level=6),
        ]
        state = reconstruct_state_from_trades(bot, trades)
        assert len(state["positions"]) == 2
        assert state["positions"][0]["entry"] == 150.0
        assert state["positions"][1]["entry"] == 140.0
        assert state["lowest_price"] == 140.0
        # Level 6 should be marked as bought
        lvl6 = [l for l in state["buy_levels"] if l["level_index"] == 6][0]
        assert lvl6["status"] == "bought"

    def test_partial_cycle(self):
        bot = make_bot(max_price=200.0, min_price=100.0, grid_levels=10)
        trades = [
            SimpleNamespace(trade_type="buy", price=150.0, quantity=0.667, created_at=1, grid_level=-1),
            SimpleNamespace(trade_type="buy", price=140.0, quantity=0.714, created_at=2, grid_level=6),
            SimpleNamespace(trade_type="sell", price=153.0, quantity=0.667, created_at=3, grid_level=-1),
            SimpleNamespace(trade_type="buy", price=130.0, quantity=0.769, created_at=4, grid_level=7),
        ]
        state = reconstruct_state_from_trades(bot, trades)
        assert len(state["positions"]) == 2
        assert state["positions"][0]["entry"] == 140.0
        assert state["positions"][1]["entry"] == 130.0

    def test_unsorted_trades(self):
        bot = make_bot(max_price=200.0, min_price=100.0, grid_levels=10)
        trades = [
            SimpleNamespace(trade_type="buy", price=140.0, quantity=0.714, created_at=2, grid_level=6),
            SimpleNamespace(trade_type="buy", price=150.0, quantity=0.667, created_at=1, grid_level=-1),
        ]
        state = reconstruct_state_from_trades(bot, trades)
        assert state["positions"][0]["entry"] == 150.0
        assert state["positions"][1]["entry"] == 140.0

    def test_sold_levels_tracked(self):
        """Sold grid levels should have status='sold' in buy_levels."""
        bot = make_bot(max_price=200.0, min_price=100.0, grid_levels=10)
        trades = [
            SimpleNamespace(trade_type="buy", price=150.0, quantity=0.667, created_at=1, grid_level=-1),
            SimpleNamespace(trade_type="buy", price=140.0, quantity=0.714, created_at=2, grid_level=6),
            SimpleNamespace(trade_type="sell", price=144.0, quantity=0.714, created_at=3, grid_level=6),
        ]
        state = reconstruct_state_from_trades(bot, trades)
        assert len(state["positions"]) == 1
        lvl6 = [l for l in state["buy_levels"] if l["level_index"] == 6][0]
        assert lvl6["status"] == "sold"


class TestReBuy:
    """Tests for re-buying at freed (sold) grid levels."""

    def test_rebuy_after_sell(self):
        """After selling a grid position, that level can be re-bought."""
        bot = make_bot(
            max_price=200.0, min_price=100.0,
            grid_levels=5, sell_percentage=2.0, total_amount=1000.0,
        )
        # Levels: [200, 180, 160, 140, 120, 100]
        prices = [
            150.0,   # BUY initial
            142.0, 139.0, 139.5, 139.3,  # BUY at level 3 (140)
            # Sell level 3
            145.0,  # 145/139.3 = 4.1% > 2%
            144.5,  # pullback -> SELL level 3
            # Price drops back to level 3
            142.0, 139.0, 139.5,
            139.3,  # RE-BUY at level 3 (sold -> bought)
        ]
        decisions, state = run_prices(bot, prices)
        buys = [d for d in decisions if d["side"] == "buy"]
        sells = [d for d in decisions if d["side"] == "sell"]
        assert len(buys) == 3  # initial + buy + re-buy
        assert len(sells) == 1
        # Level 3 should be bought again
        lvl3 = [l for l in state["buy_levels"] if l["level_index"] == 3][0]
        assert lvl3["status"] == "bought"

    def test_no_rebuy_at_pending_level_above_entry(self):
        """Pending levels above entry price should not trigger buys."""
        bot = make_bot(
            max_price=200.0, min_price=100.0,
            grid_levels=10, sell_percentage=2.0, total_amount=1000.0,
        )
        # Levels: [200,190,...,110,100]. First buy at 150 -> only levels below 150 should buy
        prices = [
            150.0,   # BUY initial
            148.0,   # drop but above level 6 (140)
            147.0,
            148.0,
            147.5,   # should NOT buy any level above 150
        ]
        decisions, state = run_prices(bot, prices)
        buys = [d for d in decisions if d["side"] == "buy"]
        assert len(buys) == 1  # only initial buy


class TestFullScenario:
    """End-to-end scenario simulating a realistic price sequence."""

    def test_full_grid_cycle(self):
        bot = make_bot(
            grid_levels=5, sell_percentage=3.0, total_amount=1000.0,
            max_price=200.0, min_price=100.0,
        )
        # Levels: [200, 180, 160, 140, 120, 100]
        prices = [
            150.0,   # BUY (first buy)
            142.0,   # below 140 (level 3)
            139.0,   # lowest
            139.5,   # bounce
            139.3,   # BUY at level 3 (140)
            122.0,   # below 120 (level 4)
            119.0,   # lowest
            119.5,   # bounce
            119.3,   # BUY at level 4 (120)
            # Recovery
            124.0,
            123.5,   # 123.5/119.3 = 3.5% gain on pos3
            123.0,   # pullback -> SELL pos3
            143.0,
            145.0,   # 145/139.3 = 4.1% > 3%, highest=145
            144.5,   # pullback -> SELL pos2
            155.0,   # 155/150 = 3.3% > 3%, highest=155
            154.5,   # pullback -> SELL pos1
        ]
        decisions, state = run_prices(bot, prices)
        buys = [d for d in decisions if d["side"] == "buy"]
        sells = [d for d in decisions if d["side"] == "sell"]
        assert len(buys) == 3
        assert len(sells) == 3
        assert len(state["positions"]) == 0

    def test_no_activity_when_price_flat(self):
        bot = make_bot()
        prices = [150.0] * 20
        decisions, state = run_prices(bot, prices)
        buys = [d for d in decisions if d["side"] == "buy"]
        assert len(buys) == 1
        assert len(state["positions"]) == 1

    def test_no_double_buy_at_grid_level(self):
        bot = make_bot(
            max_price=0.085, min_price=0.070, grid_levels=10,
            sell_percentage=2.0, total_amount=100.0,
        )
        prices = [
            0.0800,   # BUY #1
            0.0790,
            0.0780,
            0.0770,   # lowest
            0.0778,   # bounce
            0.0776,   # BUY #2
            0.0776,   # same price
            0.0774,
            0.0773,
        ]
        decisions, state = run_prices(bot, prices)
        buys = [d for d in decisions if d["side"] == "buy"]
        assert len(buys) == 2, f"Expected 2 buys, got {len(buys)}"

    def test_no_exceed_grid_levels_after_partial_sell_and_reconstruct(self):
        bot = make_bot(
            max_price=200.0, min_price=100.0, grid_levels=5,
            sell_percentage=2.0, total_amount=1000.0,
        )
        # Phase 1: buy 3 positions
        prices = [
            150.0,   # BUY #1
            142.0, 139.0, 139.5, 139.3,   # BUY #2
            122.0, 119.0, 119.5, 119.3,   # BUY #3
        ]
        decisions, state = run_prices(bot, prices)
        buys = [d for d in decisions if d["side"] == "buy"]
        assert len(buys) == 3
        assert len(state["positions"]) == 3

        # Simulate reconstruction
        fake_trades = [
            SimpleNamespace(trade_type="buy", price=150.0, quantity=1.0, created_at=1, grid_level=-1),
            SimpleNamespace(trade_type="buy", price=139.3, quantity=1.0, created_at=2, grid_level=3),
            SimpleNamespace(trade_type="buy", price=119.3, quantity=1.0, created_at=3, grid_level=4),
        ]
        state = reconstruct_state_from_trades(bot, fake_trades)
        assert len(state["positions"]) == 3

        # Phase 2: price drops further
        previous_price = 119.3
        more_buys = 0
        for p in [115.0, 110.0, 105.0, 103.0, 103.5, 103.3, 101.0, 100.5, 100.8, 100.6]:
            d, state = decide_trade(bot, p, state, previous_price)
            more_buys += sum(1 for x in d if x["side"] == "buy")
            previous_price = p

        total_positions = len(state["positions"])
        assert total_positions <= 5, f"Expected at most 5 positions, got {total_positions}"

    def test_grid_level_prevents_double_buy(self):
        bot = make_bot(
            max_price=200.0, min_price=100.0, grid_levels=5,
            sell_percentage=2.0, total_amount=1000.0,
        )
        prices = [
            150.0,   # BUY initial
            142.0, 139.0, 139.5, 139.3,   # BUY at level 3
        ]
        decisions, state = run_prices(bot, prices)
        buys = [d for d in decisions if d["side"] == "buy"]
        assert len(buys) == 2
        assert state["positions"][0]["grid_level"] == -1
        assert state["positions"][1]["grid_level"] == 3

        # Price bounces back to level 3 -> no buy (occupied)
        previous = 139.3
        for p in [141.0, 140.5, 139.0, 138.5, 139.0, 138.8]:
            d, state = decide_trade(bot, p, state, previous)
            extra_buys = [x for x in d if x["side"] == "buy"]
            assert len(extra_buys) == 0, f"Should not double-buy, price={p}"
            previous = p
        assert len(state["positions"]) == 2

    def test_grid_level_freed_after_sell(self):
        bot = make_bot(
            max_price=200.0, min_price=100.0, grid_levels=5,
            sell_percentage=2.0, total_amount=1000.0,
        )
        prices = [
            150.0,   # BUY initial
            142.0, 139.0, 139.5, 139.3,  # BUY at level 3
            145.0,  # gain > 2%
            144.5,  # pullback -> SELL
        ]
        decisions, state = run_prices(bot, prices)
        sells = [d for d in decisions if d["side"] == "sell"]
        assert len(sells) >= 1
        # Level 3 should be freed (sold status)
        lvl3 = [l for l in state["buy_levels"] if l["level_index"] == 3][0]
        assert lvl3["status"] == "sold"

    def test_hard_limit_after_reconstruct_with_many_positions(self):
        bot = make_bot(
            max_price=200.0, min_price=100.0, grid_levels=3,
            sell_percentage=5.0, total_amount=1000.0,
        )
        state = {
            "positions": [
                {"qty": 1.0, "entry": 180.0, "highest": 180.0, "fee": 0.1, "grid_level": 0},
                {"qty": 1.0, "entry": 160.0, "highest": 160.0, "fee": 0.1, "grid_level": 1},
                {"qty": 1.0, "entry": 140.0, "highest": 140.0, "fee": 0.1, "grid_level": 2},
            ],
            "lowest_price": 135.0,
            "buy_levels": _create_buy_levels_from_config(bot),
        }
        # Mark levels as bought
        for lvl in state["buy_levels"]:
            if lvl["level_index"] in (0, 1, 2):
                lvl["status"] = "bought"
        decisions, state = decide_trade(bot, 130.0, state, 135.0)
        buys = [d for d in decisions if d["side"] == "buy"]
        assert len(buys) == 0
        assert len(state["positions"]) == 3

    def test_max_positions_equals_grid_levels(self):
        bot = make_bot(
            max_price=0.085, min_price=0.070, grid_levels=10,
            sell_percentage=2.0, total_amount=100.0,
        )
        prices = [0.0800]
        p = 0.0800
        while p > 0.0700:
            p -= 0.0001
            prices.append(round(p, 5))

        decisions, state = run_prices(bot, prices)
        buys = [d for d in decisions if d["side"] == "buy"]
        assert len(buys) <= 10, f"Expected at most 10 buys, got {len(buys)}"
        assert len(state["positions"]) <= 10

    def test_real_klines_ethusdc_20260329(self):
        import json, os

        bot = make_bot(
            symbol="ETHUSDC",
            min_price=1975.0, max_price=2015.0,
            total_amount=2000.0, grid_levels=10, sell_percentage=3.0,
        )

        kline_path = os.path.join(os.path.dirname(__file__), "..", "testset.kline")
        if not os.path.exists(kline_path):
            pytest.skip("testset.kline not found")

        with open(kline_path) as f:
            try:
                raw = json.load(f)
            except json.JSONDecodeError:
                pytest.skip("testset.kline is not JSON (CSV format)")
        prices = [float(k[4]) for k in raw]

        all_decisions, state = run_prices(bot, prices)
        buys = [d for d in all_decisions if d["side"] == "buy"]

        assert len(buys) >= 1
        assert len(state["positions"]) <= bot.grid_levels
        for i in range(1, len(buys)):
            assert buys[i]["entry_price"] < buys[i-1]["entry_price"]

    def test_grid_levels_1_only_one_buy(self):
        bot = make_bot(grid_levels=1, sell_percentage=2.0)
        prices = [
            150.0,   # first buy
            140.0,
            130.0,
            153.5,   # 2.3% gain
            153.0,   # pullback -> sell
            145.0,   # restart buy
        ]
        decisions, state = run_prices(bot, prices)
        buys = [d for d in decisions if d["side"] == "buy"]
        sells = [d for d in decisions if d["side"] == "sell"]
        assert len(buys) == 2  # first + restart
        assert len(sells) == 1
