"""Fetch historical klines from Binance API or Binance Vision archives."""

import io
import logging
import zipfile
from datetime import datetime, timedelta, timezone
from urllib.request import urlopen
from urllib.error import HTTPError

logger = logging.getLogger(__name__)

VISION_BASE_URL = "https://data.binance.vision/data/spot/daily/klines"


def fetch_klines(
    symbol: str,
    interval: str = "1h",
    limit: int = 2000,
) -> list[dict]:
    """Fetch OHLCV klines from Binance, paginating if limit > 1000.

    Args:
        symbol: Trading pair (e.g., "BTCUSDT").
        interval: Candle interval (e.g., "1h", "4h", "1d").
        limit: Total number of candles to fetch (can exceed 1000).

    Returns:
        List of kline dicts sorted chronologically (oldest first).
        Each dict has keys: time, open, high, low, close, volume.
    """
    import httpx
    from app.core.config import settings

    base_url = settings.BINANCE_BASE_URL
    all_klines: list[dict] = []
    end_time: int | None = None
    remaining = limit

    with httpx.Client(timeout=15.0) as client:
        while remaining > 0:
            batch_size = min(remaining, 1000)
            params: dict = {
                "symbol": symbol.upper(),
                "interval": interval,
                "limit": batch_size,
            }
            if end_time is not None:
                params["endTime"] = end_time

            resp = client.get(f"{base_url}/api/v3/klines", params=params)
            resp.raise_for_status()
            data = resp.json()

            if not data:
                break

            batch = [
                {
                    "time": int(k[0]),
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),
                }
                for k in data
            ]

            all_klines = batch + all_klines
            remaining -= len(batch)

            if len(data) < batch_size:
                break

            # Next page: before the oldest candle in this batch
            end_time = data[0][0] - 1

    # Trim to exact limit (keep the most recent)
    if len(all_klines) > limit:
        all_klines = all_klines[-limit:]

    return all_klines


def fetch_klines_vision(
    symbol: str,
    interval: str = "1s",
    days: int = 7,
    on_progress: callable = None,
) -> list[dict]:
    """Fetch klines from Binance Vision historical data archives.

    Downloads daily ZIP/CSV files from https://data.binance.vision.
    Supports all intervals including 1s which is not available via API.
    No rate limits since it's static file hosting.

    Args:
        symbol: Trading pair (e.g., "BTCUSDC").
        interval: Candle interval (e.g., "1s", "1m", "1h").
        days: Number of past days to fetch (default: 7).
        on_progress: Optional callback(day_num, total_days, date_str).

    Returns:
        List of kline dicts sorted chronologically (oldest first).
    """
    symbol = symbol.upper()
    all_klines: list[dict] = []

    # Vision data has a ~1 day delay; start from 2 days ago to be safe
    today = datetime.now(timezone.utc).date()
    dates = [(today - timedelta(days=d)) for d in range(days + 1, 0, -1)]

    for i, date in enumerate(dates):
        date_str = date.strftime("%Y-%m-%d")
        url = f"{VISION_BASE_URL}/{symbol}/{interval}/{symbol}-{interval}-{date_str}.zip"

        if on_progress:
            on_progress(i + 1, len(dates), date_str)

        try:
            resp = urlopen(url, timeout=60)
            data = resp.read()

            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                csv_name = zf.namelist()[0]
                with zf.open(csv_name) as f:
                    for line in f:
                        parts = line.decode().strip().split(",")
                        if len(parts) < 6:
                            continue
                        # Skip header if present
                        try:
                            timestamp = int(parts[0])
                        except ValueError:
                            continue

                        # From Jan 2025: timestamps are in microseconds
                        if timestamp > 1e15:
                            timestamp = timestamp // 1000

                        all_klines.append({
                            "time": timestamp,
                            "open": float(parts[1]),
                            "high": float(parts[2]),
                            "low": float(parts[3]),
                            "close": float(parts[4]),
                            "volume": float(parts[5]),
                        })

        except HTTPError as e:
            if e.code == 404:
                logger.debug(f"No data for {symbol} {date_str} (404)")
            else:
                logger.warning(f"Failed to fetch {symbol} {date_str}: {e}")
        except (zipfile.BadZipFile, Exception) as e:
            logger.warning(f"Error processing {symbol} {date_str}: {e}")

    logger.info(f"Vision: fetched {len(all_klines)} klines for {symbol} ({interval}, {days}d)")
    return all_klines
