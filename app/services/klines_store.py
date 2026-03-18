"""Local file-based storage for klines data.

Structure: {KLINES_DATA_DIR}/{SYMBOL}/{interval}/{YYYY-MM-DD}.json
One file per day, per symbol, per candle interval.
"""

import json
import logging
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)


def _get_data_dir() -> Path:
    from app.core.config import settings
    return Path(settings.KLINES_DATA_DIR)


def get_klines_path(symbol: str, interval: str, day: date) -> Path:
    """Return the file path for a given symbol/interval/day."""
    return _get_data_dir() / symbol.upper() / interval / f"{day.isoformat()}.json"


def has_day(symbol: str, interval: str, day: date) -> bool:
    """Check if klines are stored locally for a given day."""
    return get_klines_path(symbol, interval, day).exists()


def load_day(symbol: str, interval: str, day: date) -> list[dict]:
    """Load klines from a local JSON file for a single day."""
    path = get_klines_path(symbol, interval, day)
    if not path.exists():
        return []
    with open(path, "r") as f:
        return json.load(f)


def save_day(symbol: str, interval: str, day: date, klines: list[dict]):
    """Save klines to a local JSON file for a single day."""
    path = get_klines_path(symbol, interval, day)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(klines, f)
    logger.debug(f"Saved {len(klines)} klines to {path}")


def get_missing_days(symbol: str, interval: str, days: list[date]) -> list[date]:
    """Return the dates that are not stored locally."""
    return [d for d in days if not has_day(symbol, interval, d)]


def load_days(symbol: str, interval: str, days: list[date]) -> list[dict]:
    """Load and concatenate klines for multiple days, sorted chronologically."""
    all_klines = []
    for day in sorted(days):
        all_klines.extend(load_day(symbol, interval, day))
    return all_klines
