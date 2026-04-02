"""Fetch ZROUSDC 1s klines from Binance Vision for March 29 12:00 to April 2 17:00 UTC."""

import io
import csv
import zipfile
from datetime import date, datetime, timezone
from urllib.request import urlopen
from urllib.error import HTTPError

VISION_BASE_URL = "https://data.binance.vision/data/spot/daily/klines"
SYMBOL = "ZROUSDC"
INTERVAL = "1s"

# Time range (UTC)
START = datetime(2026, 3, 29, 12, 0, 0, tzinfo=timezone.utc)
END = datetime(2026, 4, 2, 17, 0, 0, tzinfo=timezone.utc)
START_MS = int(START.timestamp() * 1000)
END_MS = int(END.timestamp() * 1000)

# Days to fetch
DAYS = [
    date(2026, 3, 29),
    date(2026, 3, 30),
    date(2026, 3, 31),
    date(2026, 4, 1),
    date(2026, 4, 2),
]

all_rows = []

for day in DAYS:
    date_str = day.strftime("%Y-%m-%d")
    url = f"{VISION_BASE_URL}/{SYMBOL}/{INTERVAL}/{SYMBOL}-{INTERVAL}-{date_str}.zip"
    print(f"Fetching {date_str}...", end=" ", flush=True)

    try:
        resp = urlopen(url, timeout=60)
        data = resp.read()
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            csv_name = zf.namelist()[0]
            with zf.open(csv_name) as f:
                count = 0
                for line in f:
                    parts = line.decode().strip().split(",")
                    if len(parts) < 6:
                        continue
                    try:
                        ts = int(parts[0])
                    except ValueError:
                        continue
                    # Microsecond timestamps (from Jan 2025)
                    if ts > 1e15:
                        ts = ts // 1000
                    if START_MS <= ts <= END_MS:
                        all_rows.append((ts, *parts[1:]))
                        count += 1
                print(f"{count} klines in range")
    except HTTPError as e:
        print(f"HTTP {e.code} - not available")
    except Exception as e:
        print(f"Error: {e}")

# Save to CSV
output = "testset.kline"
print(f"\nTotal: {len(all_rows)} klines")
print(f"Saving to {output}...")

with open(output, "w") as f:
    f.write("timestamp_ms,open,high,low,close,volume,close_time,quote_volume,trades,taker_buy_base,taker_buy_quote,ignore\n")
    for row in all_rows:
        f.write(",".join(str(x) for x in row) + "\n")

print("Done!")
