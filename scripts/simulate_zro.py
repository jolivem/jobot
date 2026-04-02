"""Simulate the grid trading strategy on ZROUSDC 1s klines with buy_levels."""

import csv
from datetime import datetime, timezone

# Bot config
MAX_PRICE = 2.1
MIN_PRICE = 1.84
GRID_LEVELS = 10
SELL_PCT = 3.0  # %
TOTAL_AMOUNT = 1000
BUY_PULLBACK_PCT = 0.002
SELL_PULLBACK_PCT = 0.002
FEE_PCT = 0.00075

def ts_str(ts_ms):
    return datetime.fromtimestamp(ts_ms/1000, tz=timezone.utc).strftime("%m/%d %H:%M:%S")

# Build buy_levels (0=max .. 10=min)
step = (MAX_PRICE - MIN_PRICE) / GRID_LEVELS
buy_levels = [
    {"level_index": i, "price": round(MAX_PRICE - i * step, 8), "status": "pending"}
    for i in range(GRID_LEVELS + 1)
]

# Load klines
klines = []
with open("testset.kline") as f:
    reader = csv.reader(f)
    next(reader)
    for row in reader:
        klines.append((int(row[0]), float(row[4])))

print(f"Loaded {len(klines)} klines")
print(f"Buy levels:")
for lvl in buy_levels:
    print(f"  [{lvl['level_index']:2d}] {lvl['price']:.3f}")
print()

# State
positions = []
lowest_price = None
previous_price = None

# Start at 15:29:38 UTC
start_ts = int(datetime(2026, 3, 29, 15, 29, 38, tzinfo=timezone.utc).timestamp() * 1000)

for ts, price in klines:
    if ts < start_ts:
        continue

    # No positions: first buy
    if not positions:
        if MIN_PRICE <= price <= MAX_PRICE:
            qty = TOTAL_AMOUNT / GRID_LEVELS / price
            positions.append({
                "qty": qty, "entry": price, "highest": price,
                "fee": qty * price * FEE_PCT, "grid_level": -1,
            })
            for lvl in buy_levels:
                lvl["status"] = "pending"
            lowest_price = price
            print(f"{ts_str(ts)} BUY #1 @ {price:.5f} qty={qty:.3f} (initial)")
        previous_price = price
        continue

    # Update lowest
    if lowest_price is None or price < lowest_price:
        lowest_price = price

    # Update highest per position
    for pos in positions:
        if price > pos["highest"]:
            pos["highest"] = price

    # Check sells
    to_close = []
    for pos in positions:
        gain_pct = price / pos["entry"] - 1.0
        if gain_pct >= SELL_PCT / 100.0:
            if price <= pos["highest"] * (1.0 - SELL_PULLBACK_PCT):
                to_close.append(pos)
                print(f"{ts_str(ts)} SELL @ {price:.5f} (entry={pos['entry']:.5f}, gain={gain_pct*100:.2f}%, lvl={pos['grid_level']})")

    for pos in to_close:
        positions.remove(pos)
        gl = pos.get("grid_level")
        if gl is not None and gl >= 0:
            for lvl in buy_levels:
                if lvl["level_index"] == gl:
                    lvl["status"] = "sold"
                    break

    if not positions:
        lowest_price = None
        for lvl in buy_levels:
            lvl["status"] = "pending"
        print(f"  -> All positions closed, reset cycle")
        previous_price = price
        continue

    # Check buys
    if previous_price is None or len(positions) >= GRID_LEVELS:
        previous_price = price
        continue

    occupied_levels = {pos.get("grid_level") for pos in positions}
    lowest_entry = min(p["entry"] for p in positions)

    if price <= MAX_PRICE and price < lowest_entry:
        for lvl in buy_levels:
            if lvl["status"] not in ("pending", "sold"):
                continue
            if lvl["level_index"] in occupied_levels:
                continue
            if price <= lvl["price"]:
                pullback_price = lowest_price * (1.0 + BUY_PULLBACK_PCT)
                if price < previous_price and price >= pullback_price:
                    qty = TOTAL_AMOUNT / GRID_LEVELS / price
                    is_rebuy = lvl["status"] == "sold"
                    lvl["status"] = "bought"
                    positions.append({
                        "qty": qty, "entry": price, "highest": price,
                        "fee": qty * price * FEE_PCT, "grid_level": lvl["level_index"],
                    })
                    lowest_price = price
                    label = "RE-BUY" if is_rebuy else "BUY"
                    print(f"{ts_str(ts)} {label} @ {price:.5f} qty={qty:.3f} (lvl={lvl['level_index']}, target={lvl['price']:.3f})")
                    break

    previous_price = price

# Final state
print(f"\n=== Final state ===")
print(f"Positions: {len(positions)}")
for p in positions:
    print(f"  lvl={p['grid_level']} entry={p['entry']:.5f} qty={p['qty']:.3f}")
print(f"lowest_price: {lowest_price}")
print(f"Buy levels:")
for lvl in buy_levels:
    print(f"  [{lvl['level_index']:2d}] {lvl['price']:.3f} -> {lvl['status']}")
