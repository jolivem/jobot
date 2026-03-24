"""LSTM slope-based trading strategy with multi-timeframe regime detection.

Timeframes are expected in order: short, medium, long (e.g. "15m,1d,1w").

Regime detection (based on medium + long term slopes):
  - BULLISH:   1d > 0 AND 1w > 0  → actively buy
  - BEARISH:   1d < 0 AND 1w < 0  → don't buy, protect positions
  - UNCERTAIN: mixed signals       → buy with half position size

Buy rules (BULLISH/UNCERTAIN only):
  - Short-term slope (15m) must be above buy_slope_threshold
  - Position size = total_amount / max_positions (halved in UNCERTAIN)

Sell rules (always active):
  - Take-profit: price >= entry * (1 + take_profit_pct / 100)
  - Stop-loss:   price <= entry * (1 - stop_loss_pct / 100)
  - Trend exit:  1d slope turns negative → sell all positions
"""

import logging
from app.models.lstm_bot import LstmBot
from app.core.config import settings

logger = logging.getLogger(__name__)


def _detect_regime(slopes: dict[str, float | None], timeframes: list[str]) -> str:
    """Detect market regime from medium and long-term slopes.

    Returns "bullish", "bearish", or "uncertain".
    """
    # Need at least 2 timeframes for regime detection
    if len(timeframes) < 2:
        # Single timeframe: use it directly
        s = slopes.get(timeframes[0])
        if s is None:
            return "uncertain"
        return "bullish" if s > 0 else "bearish"

    # Medium = second timeframe (1d), Long = last timeframe (1w)
    medium_tf = timeframes[1]
    long_tf = timeframes[-1]

    medium_slope = slopes.get(medium_tf)
    long_slope = slopes.get(long_tf)

    # If we can't read one of them, be cautious
    if medium_slope is None or long_slope is None:
        return "uncertain"

    if medium_slope > 0 and long_slope > 0:
        return "bullish"
    elif medium_slope < 0 and long_slope < 0:
        return "bearish"
    else:
        return "uncertain"


def decide_trade(
    bot: LstmBot,
    current_price: float,
    slopes: dict[str, float | None],
    state: dict,
) -> tuple[list[dict], dict]:
    """Decide whether to buy, sell, or do nothing based on slope predictions.

    Args:
        bot: The LSTM bot configuration.
        current_price: Current market price from Redis.
        slopes: Predicted slopes per timeframe, e.g. {"15m": 0.5, "1d": 1.2, "1w": 0.8}.
        state: Runtime state from Redis (positions list).

    Returns:
        (decisions, updated_state) where decisions is a list of
        {"side": "buy"|"sell", "quantity": float, "entry_price": float}.
    """
    positions = state.get("positions", [])
    decisions = []
    fee_pct = settings.FEE_PCT

    # Filter out timeframes where prediction failed
    valid_slopes = {tf: s for tf, s in slopes.items() if s is not None}
    if not valid_slopes:
        return decisions, state

    timeframes = bot.timeframes.split(",")
    short_tf = timeframes[0]  # e.g. "15m"
    regime = _detect_regime(valid_slopes, timeframes)

    # === SELL checks (always active) ===
    to_close = []
    for pos in positions:
        gain_pct = (current_price / pos["entry"] - 1.0) * 100.0
        reason = None

        # Take-profit
        if gain_pct >= bot.take_profit_pct:
            reason = f"take-profit ({gain_pct:.2f}% >= {bot.take_profit_pct}%)"

        # Stop-loss
        elif gain_pct <= -bot.stop_loss_pct:
            reason = f"stop-loss ({gain_pct:.2f}% <= -{bot.stop_loss_pct}%)"

        # Trend exit: medium-term slope turns negative
        elif len(timeframes) >= 2:
            medium_slope = valid_slopes.get(timeframes[1])
            if medium_slope is not None and medium_slope < bot.sell_slope_threshold:
                reason = f"trend-exit (1d slope={medium_slope:.4f} < {bot.sell_slope_threshold})"

        if reason:
            gain_usdc = (current_price - pos["entry"]) * pos["qty"]
            decisions.append({
                "side": "sell",
                "quantity": pos["qty"],
                "entry_price": current_price,
                "buy_entry": pos["entry"],
            })
            to_close.append(pos)
            logger.info(
                f"LstmBot {bot.id}: SELL @ {current_price:.8f} "
                f"(reason: {reason}, gain: {gain_usdc:.4f} USDC, "
                f"regime: {regime})"
            )

    for pos in to_close:
        positions.remove(pos)

    # === BUY checks ===
    # Never buy in bearish regime
    if regime == "bearish":
        state["positions"] = positions
        state["regime"] = regime
        return decisions, state

    # Don't buy in the same tick we sold
    if to_close:
        state["positions"] = positions
        state["regime"] = regime
        return decisions, state

    # Check capacity
    if len(positions) >= bot.max_positions:
        state["positions"] = positions
        state["regime"] = regime
        return decisions, state

    # Short-term slope must confirm momentum
    short_slope = valid_slopes.get(short_tf)
    if short_slope is None or short_slope <= bot.buy_slope_threshold:
        state["positions"] = positions
        state["regime"] = regime
        return decisions, state

    # Position sizing: halved in uncertain regime
    position_amount = bot.total_amount / bot.max_positions
    if regime == "uncertain":
        position_amount /= 2.0

    qty = position_amount / current_price
    decisions.append({
        "side": "buy",
        "quantity": qty,
        "entry_price": current_price,
    })
    positions.append({
        "qty": qty,
        "entry": current_price,
        "fee": qty * current_price * fee_pct,
    })
    logger.info(
        f"LstmBot {bot.id}: BUY @ {current_price:.8f} "
        f"(regime: {regime}, slopes: {valid_slopes}, "
        f"positions: {len(positions)}, size: {position_amount:.2f} USDC)"
    )

    state["positions"] = positions
    state["regime"] = regime
    return decisions, state
