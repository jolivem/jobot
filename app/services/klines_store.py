"""Local file-based storage for klines data.

Structure: {KLINES_DATA_DIR}/{SYMBOL}/{interval}/{YYYY-MM-DD}.csv
One CSV file per day, per symbol, per candle interval.
Each line: timestamp_ms,open,high,low,close,volume,...,buy_quote_volume,...
"""

import json
import logging
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

# CSV columns used when reading klines
_COLS = ("time", "open", "high", "low", "close", "volume")


def _get_data_dir() -> Path:
    from app.core.config import settings
    return Path(settings.KLINES_DATA_DIR)


def _csv_path(symbol: str, interval: str, day: date) -> Path:
    return _get_data_dir() / symbol.upper() / interval / f"{day.isoformat()}.csv"


def _json_path(symbol: str, interval: str, day: date) -> Path:
    return _get_data_dir() / symbol.upper() / interval / f"{day.isoformat()}.json"


def get_klines_path(symbol: str, interval: str, day: date) -> Path:
    """Return the file path for a given symbol/interval/day (CSV preferred)."""
    csv = _csv_path(symbol, interval, day)
    if csv.exists():
        return csv
    return _json_path(symbol, interval, day)


def has_day(symbol: str, interval: str, day: date) -> bool:
    """Check if klines are stored locally for a given day."""
    return _csv_path(symbol, interval, day).exists() or _json_path(symbol, interval, day).exists()


def save_day(symbol: str, interval: str, day: date, csv_text: str):
    """Save raw CSV text for a single day."""
    path = _csv_path(symbol, interval, day)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(csv_text)
    logger.debug(f"Saved klines CSV to {path} ({len(csv_text)} bytes)")


def _parse_csv_line(line: str) -> dict | None:
    """Parse a single CSV line into a kline dict."""
    parts = line.strip().split(",")
    if len(parts) < 6:
        return None
    try:
        ts = int(parts[0])
    except ValueError:
        return None
    # Binance Vision uses microseconds since Jan 2025
    if ts > 1e15:
        ts = ts // 1000
    return {
        "time": ts,
        "open": float(parts[1]),
        "high": float(parts[2]),
        "low": float(parts[3]),
        "close": float(parts[4]),
        "volume": float(parts[5]),
        "buy_quote_volume": float(parts[10]) if len(parts) > 10 else 0.0,
    }


def load_day(symbol: str, interval: str, day: date) -> list[dict]:
    """Load klines for a single day (CSV preferred, JSON fallback)."""
    csv = _csv_path(symbol, interval, day)
    if csv.exists():
        klines = []
        with open(csv, "r") as f:
            for line in f:
                k = _parse_csv_line(line)
                if k:
                    klines.append(k)
        return klines

    # JSON fallback for old cached data
    json_path = _json_path(symbol, interval, day)
    if json_path.exists():
        with open(json_path, "r") as f:
            return json.load(f)

    return []


def get_missing_days(symbol: str, interval: str, days: list[date]) -> list[date]:
    """Return the dates that are not stored locally."""
    return [d for d in days if not has_day(symbol, interval, d)]


def load_days(symbol: str, interval: str, days: list[date]) -> list[dict]:
    """Load and concatenate klines for multiple days, sorted chronologically."""
    all_klines = []
    for day in sorted(days):
        all_klines.extend(load_day(symbol, interval, day))
    return all_klines
