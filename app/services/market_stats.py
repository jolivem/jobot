"""Market statistics computed from historical price data."""

import math


def compute_market_stats(klines: list[dict]) -> dict:
    """Compute statistical indicators from OHLCV klines.

    Args:
        klines: List of kline dicts with keys: close, high, low.

    Returns:
        Dict with keys: trend_pct, volatility_pct, range_pct,
        stddev_pct, adr_pct, mean_reversion.
    """
    closes = [k["close"] for k in klines]
    n = len(closes)

    if n < 2:
        return {
            "trend_pct": 0.0,
            "volatility_pct": 0.0,
            "range_pct": 0.0,
            "stddev_pct": 0.0,
            "adr_pct": 0.0,
            "mean_reversion": 0.0,
        }

    mean_price = sum(closes) / n

    # --- Trend% : linear regression slope, normalized ---
    # slope = sum((i - mean_i) * (p - mean_p)) / sum((i - mean_i)^2)
    mean_i = (n - 1) / 2.0
    num = 0.0
    den = 0.0
    for i, p in enumerate(closes):
        di = i - mean_i
        num += di * (p - mean_price)
        den += di * di
    slope = num / den if den != 0 else 0.0
    # Normalize: total change over the period as % of mean
    trend_pct = (slope * (n - 1)) / mean_price * 100.0 if mean_price != 0 else 0.0

    # --- Returns for volatility and mean-reversion ---
    returns = []
    for i in range(1, n):
        if closes[i - 1] != 0:
            returns.append((closes[i] - closes[i - 1]) / closes[i - 1])

    nr = len(returns)

    # --- Vol% : annualized volatility ---
    if nr >= 2:
        mean_ret = sum(returns) / nr
        var_ret = sum((r - mean_ret) ** 2 for r in returns) / (nr - 1)
        std_ret = math.sqrt(var_ret)
        # Annualize: assume 1m candles = 525600/year, 1h = 8760, 1d = 365
        # Use sqrt(periods_per_year). Default to 1m assumption.
        # The caller can interpret based on interval, but for screening
        # comparisons the relative ranking is what matters.
        volatility_pct = std_ret * math.sqrt(525600) * 100.0
    else:
        volatility_pct = 0.0

    # --- Range% : (max - min) / mean ---
    min_close = min(closes)
    max_close = max(closes)
    range_pct = (max_close - min_close) / mean_price * 100.0 if mean_price != 0 else 0.0

    # --- StdDev% : coefficient of variation ---
    variance = sum((p - mean_price) ** 2 for p in closes) / (n - 1)
    stddev_pct = math.sqrt(variance) / mean_price * 100.0 if mean_price != 0 else 0.0

    # --- ADR% : Average Daily Range using high/low ---
    # Group klines by approximate day (every 1440 for 1m candles)
    # Simpler: compute average (high - low) / midpoint for each candle
    adr_values = []
    for k in klines:
        h = k.get("high", k["close"])
        l = k.get("low", k["close"])
        mid = (h + l) / 2.0
        if mid > 0:
            adr_values.append((h - l) / mid)
    adr_pct = (sum(adr_values) / len(adr_values) * 100.0) if adr_values else 0.0

    # --- MeanRev : lag-1 autocorrelation of returns ---
    # Negative = mean-reverting (good for grid), Positive = trending
    if nr >= 3:
        mean_ret = sum(returns) / nr
        var_sum = sum((r - mean_ret) ** 2 for r in returns)
        if var_sum > 0:
            cov_sum = sum(
                (returns[i] - mean_ret) * (returns[i + 1] - mean_ret)
                for i in range(nr - 1)
            )
            mean_reversion = cov_sum / var_sum
        else:
            mean_reversion = 0.0
    else:
        mean_reversion = 0.0

    return {
        "trend_pct": round(trend_pct, 2),
        "volatility_pct": round(volatility_pct, 2),
        "range_pct": round(range_pct, 2),
        "stddev_pct": round(stddev_pct, 2),
        "adr_pct": round(adr_pct, 4),
        "mean_reversion": round(mean_reversion, 4),
    }
