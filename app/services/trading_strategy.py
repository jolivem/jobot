"""Trading strategy placeholder.

Replace the `decide_trade` function with your actual trading algorithm.
The function receives the bot configuration and the current market price,
and returns a trade decision or None.
"""

from app.models.trading_bot import TradingBot


def decide_trade(bot: TradingBot, current_price: float) -> dict | None:
    """Decide whether to buy, sell, or do nothing.

    Args:
        bot: The trading bot with its configuration (min_price, max_price,
             total_amount, buy_percentage, sell_percentage).
        current_price: Current market price of the symbol from Redis.

    Returns:
        A dict {"side": "buy"|"sell", "quantity": float} if a trade should
        be executed, or None to skip this tick.
    """
    # TODO: Implement actual trading algorithm here.
    # Available bot params: bot.min_price, bot.max_price, bot.total_amount,
    #                       bot.buy_percentage, bot.sell_percentage
    return None
