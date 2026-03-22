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
from app.services.trading_strategy import decide_trade, compute_grid, reconstruct_state_from_trades


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


def empty_state():
    return {"positions": [], "lowest_price": None, "grid_prices": [], "next_grid_index": 0}


def run_prices(bot, prices):
    """Run a sequence of prices through the strategy and return all decisions."""
    state = empty_state()
    previous_price = None
    all_decisions = []
    for price in prices:
        decisions, state = decide_trade(bot, price, state, previous_price)
        for d in decisions:
            all_decisions.append({**d, "price_at_tick": price})
        previous_price = price
    return all_decisions, state


class TestComputeGrid:
    """Tests for the compute_grid utility function."""

    def test_basic_grid(self):
        """10 levels from 150 to 100: 9 additional levels."""
        grid = compute_grid(150.0, 100.0, 10)
        assert len(grid) == 9
        # step = (150 - 100) / 10 = 5
        assert grid[0] == pytest.approx(145.0)
        assert grid[1] == pytest.approx(140.0)
        assert grid[-1] == pytest.approx(105.0)

    def test_grid_two_levels(self):
        """2 levels: only 1 additional level."""
        grid = compute_grid(150.0, 100.0, 2)
        assert len(grid) == 1
        # step = (150 - 100) / 2 = 25
        assert grid[0] == pytest.approx(125.0)

    def test_grid_one_level(self):
        """1 level: no additional levels."""
        grid = compute_grid(150.0, 100.0, 1)
        assert grid == []

    def test_grid_first_buy_at_min(self):
        """first_buy_price <= min_price: no grid."""
        grid = compute_grid(100.0, 100.0, 10)
        assert grid == []

    def test_grid_first_buy_below_min(self):
        grid = compute_grid(90.0, 100.0, 10)
        assert grid == []

    def test_five_levels(self):
        grid = compute_grid(200.0, 100.0, 5)
        assert len(grid) == 4
        # step = (200 - 100) / 5 = 20
        assert grid == pytest.approx([180.0, 160.0, 140.0, 120.0])


class TestFirstBuy:
    """Tests for the initial buy behavior."""

    def test_first_tick_buys_when_between_min_and_max_price(self):
        bot = make_bot(max_price=200.0, min_price=100.0, grid_levels=10)
        state = empty_state()
        decisions, state = decide_trade(bot, 150.0, state, None)
        assert len(decisions) == 1
        assert decisions[0]["side"] == "buy"
        assert decisions[0]["entry_price"] == 150.0
        assert len(state["positions"]) == 1
        # Grid should be computed from max_price
        assert len(state["grid_prices"]) == 9
        # First grid level below 150 is 140 at index 5
        assert state["next_grid_index"] == 5

    def test_first_tick_no_buy_when_above_max_price(self):
        bot = make_bot(max_price=100.0, min_price=50.0)
        state = empty_state()
        decisions, state = decide_trade(bot, 150.0, state, None)
        assert len(decisions) == 0
        assert len(state["positions"]) == 0

    def test_first_tick_no_buy_when_below_min_price(self):
        bot = make_bot(max_price=200.0, min_price=100.0)
        state = empty_state()
        decisions, state = decide_trade(bot, 90.0, state, None)
        assert len(decisions) == 0
        assert len(state["positions"]) == 0

    def test_quantity_is_total_amount_divided_by_grid_levels_and_price(self):
        bot = make_bot(total_amount=1000.0, grid_levels=10)
        state = empty_state()
        decisions, _ = decide_trade(bot, 100.0, state, None)
        # qty = 1000 / 10 / 100 = 1.0
        assert decisions[0]["quantity"] == pytest.approx(1.0, rel=1e-6)

    def test_grid_computed_from_max_price(self):
        """Grid is computed from max_price=200 to min_price=100, not from first buy."""
        bot = make_bot(max_price=200.0, min_price=100.0, grid_levels=10)
        state = empty_state()
        _, state = decide_trade(bot, 150.0, state, None)
        # step = (200 - 100) / 10 = 10
        assert state["grid_prices"] == pytest.approx([190, 180, 170, 160, 150, 140, 130, 120, 110])


class TestGridBuy:
    """Tests for grid buy at fixed price levels with pullback confirmation."""

    def test_buy_at_first_grid_level_with_pullback(self):
        """First buy at 150, next grid target = 140. Price drops to 139, bounces, buy."""
        bot = make_bot(max_price=200.0, min_price=100.0, grid_levels=10)
        # Grid: [190, 180, 170, 160, 150, 140, 130, 120, 110], next_index=5 (target=140)
        prices = [
            150.0,   # first buy
            142.0,   # tracking
            140.0,   # at grid level, but no pullback yet
            139.0,   # below grid, lowest_price = 139
            139.4,   # bounce: 139.4 >= 139.0 * 1.002 = 139.278
            139.3,   # 139.3 < 139.4 (prev) and >= pullback -> BUY
        ]
        decisions, state = run_prices(bot, prices)
        buys = [d for d in decisions if d["side"] == "buy"]
        assert len(buys) == 2
        assert buys[1]["entry_price"] == 139.3
        assert state["next_grid_index"] == 6

    def test_no_buy_without_pullback(self):
        """Price drops to grid level but keeps falling, no pullback -> no buy."""
        bot = make_bot(max_price=200.0, min_price=100.0, grid_levels=10)
        # Grid target after first buy at 150 is 140 (index 5)
        prices = [
            150.0,   # first buy
            142.0,
            140.0,   # at grid level
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
        # Grid: step=(200-100)/5=20, levels=[180, 160, 140, 120]
        # First buy at 150, next_index=2 (target=140)
        prices = [
            150.0,   # first buy
            142.0,   # below 140
            139.0,   # lowest
            139.5,   # bounce
            139.3,   # BUY at grid level 2 (140)
            122.0,   # below 120
            119.0,   # lowest
            119.5,   # bounce
            119.3,   # BUY at grid level 3 (120)
        ]
        decisions, state = run_prices(bot, prices)
        buys = [d for d in decisions if d["side"] == "buy"]
        assert len(buys) == 3
        assert state["next_grid_index"] == 4

    def test_grid_buy_respects_max_price(self):
        """No grid buy when price > max_price."""
        bot = make_bot(max_price=145.0, min_price=100.0, grid_levels=5)
        # Grid: step=(145-100)/5=9, levels=[136, 127, 118, 109]
        # First buy at 140, next_index=0 (target=136)
        prices = [
            140.0,   # first buy (between min=100 and max=145)
            137.0,
            135.0,   # below 136
            135.5,   # bounce
            135.3,   # BUY (price 135.3 < max_price 145)
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
        """Sell decisions must include buy_entry matching the position's entry price."""
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
        # New grid should be computed from the restart price
        assert len(state["grid_prices"]) > 0

    def test_no_restart_buy_above_max_price(self):
        """After all sold, no new buy if price > max_price."""
        bot = make_bot(sell_percentage=2.0, max_price=100.0, min_price=90.0)
        prices = [
            99.0,    # first buy (min=90 <= 99 <= max=100)
            101.5,   # gain > 2%, highest
            101.0,   # pullback -> sell
            101.0,   # no positions, but price > max_price -> no buy
        ]
        decisions, state = run_prices(bot, prices)
        buys = [d for d in decisions if d["side"] == "buy"]
        assert len(buys) == 1  # only first buy, no restart

    def test_grid_always_from_max_price(self):
        """Grid is always computed from max_price, regardless of buy price."""
        bot = make_bot(sell_percentage=2.0, max_price=200.0, min_price=50.0, grid_levels=5)
        prices = [
            100.0,   # first buy
            102.5,   # gain
            102.0,   # sell
            80.0,    # restart buy at 80
        ]
        decisions, state = run_prices(bot, prices)
        # Grid always from max_price: step = (200 - 50) / 5 = 30 -> [170, 140, 110, 80]
        assert state["grid_prices"] == pytest.approx([170.0, 140.0, 110.0, 80.0])


class TestMultiplePositions:
    """Tests for managing multiple grid positions simultaneously."""

    def test_independent_sell_per_position(self):
        """Each position sells independently based on its own entry price."""
        bot = make_bot(grid_levels=5, sell_percentage=2.0, max_price=200.0, min_price=100.0)
        # Grid: step=20, levels=[180, 160, 140, 120]
        # First buy at 150, next_index=2 (target=140)
        prices = [
            150.0,   # BUY #1 at 150
            142.0,   # below 140
            139.0,   # lowest
            139.5,   # bounce
            139.3,   # BUY #2 at grid level 2 (140)
            142.5,   # rising - 142.5/139.3 = 2.3% on pos2, highest=142.5
            142.0,   # pullback from 142.5: 142.0 <= 142.5*0.998=142.215 -> SELL pos2
            153.5,   # 153.5/150 = 2.3% gain on pos1, highest=153.5
            153.0,   # pullback -> SELL pos1
        ]
        decisions, state = run_prices(bot, prices)
        buys = [d for d in decisions if d["side"] == "buy"]
        sells = [d for d in decisions if d["side"] == "sell"]
        assert len(buys) == 2
        assert len(sells) == 2
        assert len(state["positions"]) == 0
        # Each sell references its own buy entry price
        sell_buy_entries = sorted([s["buy_entry"] for s in sells])
        assert sell_buy_entries == pytest.approx([139.3, 150.0])

    def test_no_duplicate_buy_at_same_level(self):
        """After buying at a grid level, should not buy again at same level."""
        bot = make_bot(max_price=200.0, min_price=100.0, grid_levels=10)
        # Grid: [190,180,170,160,150,140,130,120,110], next_index=5 after first buy at 150
        state = empty_state()

        # First buy at 150
        decisions, state = decide_trade(bot, 150.0, state, None)
        assert len(decisions) == 1

        # Drop to grid level 5 (140), bounce, buy
        _, state = decide_trade(bot, 139.0, state, 150.0)
        _, state = decide_trade(bot, 139.5, state, 139.0)  # bounce
        decisions, state = decide_trade(bot, 139.3, state, 139.5)  # BUY
        assert len(decisions) == 1
        assert state["next_grid_index"] == 6

        # Price comes back to same level -> no buy (next target is 130, not 140)
        _, state = decide_trade(bot, 140.0, state, 139.3)
        _, state = decide_trade(bot, 139.0, state, 140.0)
        decisions, state = decide_trade(bot, 139.3, state, 139.5)
        assert len(decisions) == 0

    def test_lowest_price_reset_after_first_buy(self):
        """lowest_price should be set to buy price after the first buy."""
        bot = make_bot()
        state = empty_state()

        # First buy
        _, state = decide_trade(bot, 150.0, state, None)
        assert state["lowest_price"] == 150.0

        # Price drops, lowest_price tracks
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
        assert state["grid_prices"] == []
        assert state["next_grid_index"] == 0

    def test_all_sold(self):
        """All buys matched by sells -> empty state."""
        bot = make_bot()
        trades = [
            SimpleNamespace(trade_type="buy", price=150.0, quantity=0.667, created_at=1),
            SimpleNamespace(trade_type="sell", price=153.0, quantity=0.667, created_at=2),
        ]
        state = reconstruct_state_from_trades(bot, trades)
        assert state["positions"] == []
        assert state["grid_prices"] == []

    def test_open_positions(self):
        """2 buys, 0 sells -> 2 open positions, grid reconstructed."""
        bot = make_bot(max_price=200.0, min_price=100.0, grid_levels=10)
        trades = [
            SimpleNamespace(trade_type="buy", price=150.0, quantity=0.667, created_at=1),
            SimpleNamespace(trade_type="buy", price=140.0, quantity=0.714, created_at=2),
        ]
        state = reconstruct_state_from_trades(bot, trades)
        assert len(state["positions"]) == 2
        assert state["positions"][0]["entry"] == 150.0
        assert state["positions"][1]["entry"] == 140.0
        # Grid reconstructed from max_price
        assert len(state["grid_prices"]) == 9
        assert state["grid_prices"][0] == pytest.approx(190.0)
        # start_index = 5 (first level < 150 is 140), + 1 grid buy = 6
        assert state["next_grid_index"] == 6
        assert state["lowest_price"] == 140.0

    def test_partial_cycle(self):
        """3 buys, 1 sell (FIFO) -> 2 open positions."""
        bot = make_bot(max_price=200.0, min_price=100.0, grid_levels=10)
        trades = [
            SimpleNamespace(trade_type="buy", price=150.0, quantity=0.667, created_at=1),
            SimpleNamespace(trade_type="buy", price=140.0, quantity=0.714, created_at=2),
            SimpleNamespace(trade_type="sell", price=153.0, quantity=0.667, created_at=3),
            SimpleNamespace(trade_type="buy", price=130.0, quantity=0.769, created_at=4),
        ]
        state = reconstruct_state_from_trades(bot, trades)
        # FIFO: sell removes first buy (150). Remaining: 140, 130
        assert len(state["positions"]) == 2
        assert state["positions"][0]["entry"] == 140.0
        assert state["positions"][1]["entry"] == 130.0
        # Grid from max_price
        grid = compute_grid(200.0, 100.0, 10)
        assert state["grid_prices"] == pytest.approx(grid)
        # start_index for 140: first level < 140 is 130 at index 6. + 1 grid buy = 7
        assert state["next_grid_index"] == 7

    def test_unsorted_trades(self):
        """Trades passed in wrong order are sorted internally."""
        bot = make_bot(max_price=200.0, min_price=100.0, grid_levels=10)
        trades = [
            SimpleNamespace(trade_type="buy", price=140.0, quantity=0.714, created_at=2),
            SimpleNamespace(trade_type="buy", price=150.0, quantity=0.667, created_at=1),
        ]
        state = reconstruct_state_from_trades(bot, trades)
        # After sorting: buy@150 (first), buy@140 (second)
        assert state["positions"][0]["entry"] == 150.0
        assert state["positions"][1]["entry"] == 140.0


class TestFullScenario:
    """End-to-end scenario simulating a realistic price sequence."""

    def test_full_grid_cycle(self):
        """Simulate: first buy -> grid buys on dips -> sell all on recovery."""
        bot = make_bot(
            grid_levels=5,
            sell_percentage=3.0,
            total_amount=1000.0,
            max_price=200.0,
            min_price=100.0,
        )
        # Grid: step=(200-100)/5=20, levels=[180, 160, 140, 120]
        # First buy at 150, next_index=2 (target=140)
        prices = [
            150.0,   # BUY (first buy)
            142.0,   # below 140
            139.0,   # lowest
            139.5,   # bounce
            139.3,   # BUY #2 at grid level 2 (140)
            122.0,   # below 120
            119.0,   # lowest
            119.5,   # bounce
            119.3,   # BUY #3 at grid level 3 (120)
            # Recovery
            124.0,
            123.5,   # 123.5/119.3 = 3.5% gain on pos3
            123.0,   # pullback -> SELL pos3
            143.0,   # 143/139.3 = 2.7% < 3%, not enough for pos2
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
        assert len(state["positions"]) == 0  # all sold

    def test_no_activity_when_price_flat(self):
        """If price stays flat, only the initial buy happens."""
        bot = make_bot()
        prices = [150.0] * 20
        decisions, state = run_prices(bot, prices)
        buys = [d for d in decisions if d["side"] == "buy"]
        assert len(buys) == 1  # only initial buy
        assert len(state["positions"]) == 1

    def test_no_double_buy_at_grid_level(self):
        """When price crosses a grid level, only ONE buy should trigger, not two."""
        bot = make_bot(
            max_price=0.085,
            min_price=0.070,
            grid_levels=10,
            sell_percentage=2.0,
            total_amount=100.0,
        )
        # step = (0.085-0.070)/10 = 0.0015 (~2% of 0.075)
        # grid levels: 0.0835, 0.082, 0.0805, 0.079, 0.0775, 0.076, 0.0745, 0.073, 0.0715
        # First buy at 0.080, next target should be 0.079 or below
        prices = [
            0.0800,   # BUY #1 (initial)
            0.0790,   # drop
            0.0780,   # drop through grid level
            0.0770,   # lowest
            0.0778,   # bounce (+1%)
            0.0776,   # dip -> BUY #2 (one grid buy)
            0.0776,   # same price, should NOT buy again
            0.0774,   # small dip, should NOT buy (too close to #2)
            0.0773,   # small dip, should NOT buy
        ]
        decisions, state = run_prices(bot, prices)
        buys = [d for d in decisions if d["side"] == "buy"]
        assert len(buys) == 2, f"Expected 2 buys, got {len(buys)}"

    def test_no_exceed_grid_levels_after_partial_sell_and_reconstruct(self):
        """After selling some positions and reconstructing state (Redis restart),
        the bot should never exceed grid_levels open positions."""
        bot = make_bot(
            max_price=200.0,
            min_price=100.0,
            grid_levels=5,
            sell_percentage=2.0,
            total_amount=1000.0,
        )
        # step=20, grid=[180,160,140,120]
        # Phase 1: buy 3 positions
        prices = [
            150.0,   # BUY #1
            142.0, 139.0, 139.5, 139.3,   # BUY #2 at 140
            122.0, 119.0, 119.5, 119.3,   # BUY #3 at 120
        ]
        decisions, state = run_prices(bot, prices)
        buys = [d for d in decisions if d["side"] == "buy"]
        assert len(buys) == 3
        assert len(state["positions"]) == 3

        # Simulate reconstruction (Redis restart) with 3 open positions
        # This resets next_grid_index based on open positions count
        fake_trades = [
            SimpleNamespace(trade_type="buy", price=150.0, quantity=1.0, created_at=1),
            SimpleNamespace(trade_type="buy", price=139.3, quantity=1.0, created_at=2),
            SimpleNamespace(trade_type="buy", price=119.3, quantity=1.0, created_at=3),
        ]
        state = reconstruct_state_from_trades(bot, fake_trades)
        assert len(state["positions"]) == 3

        # Phase 2: continue trading from reconstructed state — price drops further
        previous_price = 119.3
        more_buys = 0
        for p in [115.0, 110.0, 105.0, 103.0, 103.5, 103.3, 101.0, 100.5, 100.8, 100.6]:
            d, state = decide_trade(bot, p, state, previous_price)
            more_buys += sum(1 for x in d if x["side"] == "buy")
            previous_price = p

        total_positions = len(state["positions"])
        assert total_positions <= 5, f"Expected at most 5 positions, got {total_positions}"

    def test_grid_level_prevents_double_buy(self):
        """A grid level already occupied by an open position cannot trigger a second buy."""
        bot = make_bot(
            max_price=200.0,
            min_price=100.0,
            grid_levels=5,
            sell_percentage=2.0,
            total_amount=1000.0,
        )
        # step=20, grid=[180,160,140,120]
        # Buy initial, then grid buy at level 140
        prices = [
            150.0,   # BUY initial (grid_level=-1)
            142.0, 139.0, 139.5, 139.3,   # BUY at grid level (grid_level=2)
        ]
        decisions, state = run_prices(bot, prices)
        buys = [d for d in decisions if d["side"] == "buy"]
        assert len(buys) == 2

        # Verify grid_level is stored
        assert state["positions"][0]["grid_level"] == -1
        assert state["positions"][1]["grid_level"] == 2

        # Price bounces back to 140 level then drops again — should NOT buy at same level
        previous = 139.3
        for p in [141.0, 140.5, 139.0, 138.5, 139.0, 138.8]:
            d, state = decide_trade(bot, p, state, previous)
            extra_buys = [x for x in d if x["side"] == "buy"]
            assert len(extra_buys) == 0, f"Should not double-buy at same grid level, price={p}"
            previous = p

        assert len(state["positions"]) == 2

    def test_grid_level_freed_after_sell(self):
        """After selling a position, its grid level is freed and can be reused."""
        bot = make_bot(
            max_price=200.0,
            min_price=100.0,
            grid_levels=5,
            sell_percentage=2.0,
            total_amount=1000.0,
        )
        # Buy initial + grid buy at 140
        prices = [
            150.0,   # BUY initial
            142.0, 139.0, 139.5, 139.3,  # BUY at grid ~140
            # Price rises → sell the grid position (#2, LIFO in sell check)
            145.0,  # gain from 139.3 = 4.1% > 2%
            144.5,  # pullback → SELL
        ]
        decisions, state = run_prices(bot, prices)
        buys = [d for d in decisions if d["side"] == "buy"]
        sells = [d for d in decisions if d["side"] == "sell"]
        assert len(buys) == 2
        assert len(sells) >= 1
        # Grid level 2 is now freed (position sold)
        occupied = {p.get("grid_level") for p in state["positions"]}
        assert 2 not in occupied

    def test_hard_limit_after_reconstruct_with_many_positions(self):
        """Even if reconstruction leaves next_grid_index allowing more buys,
        the hard limit len(positions) < grid_levels must prevent excess."""
        bot = make_bot(
            max_price=200.0,
            min_price=100.0,
            grid_levels=3,
            sell_percentage=5.0,
            total_amount=1000.0,
        )
        # Manually create a state with 3 positions (= grid_levels) but next_grid_index
        # still has room (simulating a buggy reconstruction)
        state = {
            "positions": [
                {"qty": 1.0, "entry": 180.0, "highest": 180.0, "fee": 0.1},
                {"qty": 1.0, "entry": 160.0, "highest": 160.0, "fee": 0.1},
                {"qty": 1.0, "entry": 140.0, "highest": 140.0, "fee": 0.1},
            ],
            "lowest_price": 135.0,
            "grid_prices": compute_grid(200.0, 100.0, 3),  # [166.67, 133.33]
            "next_grid_index": 1,  # still has room in grid
        }
        # Price drops further — should NOT buy because already at grid_levels positions
        decisions, state = decide_trade(bot, 130.0, state, 135.0)
        buys = [d for d in decisions if d["side"] == "buy"]
        assert len(buys) == 0, f"Should not buy when at grid_levels positions, got {len(buys)}"
        assert len(state["positions"]) == 3

    def test_max_positions_equals_grid_levels(self):
        """Never more than grid_levels open positions, even with fast price drops."""
        bot = make_bot(
            max_price=0.085,
            min_price=0.070,
            grid_levels=10,
            sell_percentage=2.0,
            total_amount=100.0,
        )
        # Price drops from 0.080 all the way down through all grid levels
        prices = [0.0800]  # initial buy
        # Drop tick by tick from 0.080 to 0.070
        p = 0.0800
        while p > 0.0700:
            p -= 0.0001
            prices.append(round(p, 5))

        decisions, state = run_prices(bot, prices)
        buys = [d for d in decisions if d["side"] == "buy"]
        assert len(buys) <= 10, f"Expected at most 10 buys, got {len(buys)}"
        assert len(state["positions"]) <= 10

    def test_grid_levels_1_only_one_buy(self):
        """With grid_levels=1, only one buy per cycle, no grid."""
        bot = make_bot(grid_levels=1, sell_percentage=2.0)
        prices = [
            150.0,   # first buy
            140.0,   # drop, but no grid levels
            130.0,   # more drop
            153.5,   # 2.3% gain
            153.0,   # pullback -> sell
            145.0,   # restart buy
        ]
        decisions, state = run_prices(bot, prices)
        buys = [d for d in decisions if d["side"] == "buy"]
        sells = [d for d in decisions if d["side"] == "sell"]
        assert len(buys) == 2  # first + restart
        assert len(sells) == 1
        assert state["grid_prices"] == []  # no grid with 1 level
