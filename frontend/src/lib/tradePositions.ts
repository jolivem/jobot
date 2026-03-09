import type { Trade } from "./api";

/**
 * Returns a map of trade.id -> position number (#1, #2, …).
 * Same logic as the trades page: buy positions increment and reset after full cycle.
 * Sells inherit the position of their matched buy.
 */
export function computeTradePositionNumbers(trades: Trade[]): Map<number, number> {
  const byBot: Record<number, Trade[]> = {};
  for (const t of trades) {
    if (!byBot[t.trading_bot_id]) byBot[t.trading_bot_id] = [];
    byBot[t.trading_bot_id].push(t);
  }

  const posMap = new Map<number, number>();

  for (const botId of Object.keys(byBot)) {
    const botTrades = byBot[parseInt(botId)].slice().reverse(); // chronological
    let buyPosition = 0;
    const openBuys: { position: number; price: number }[] = [];

    for (const t of botTrades) {
      if (t.trade_type === "buy") {
        buyPosition++;
        posMap.set(t.id, buyPosition);
        openBuys.push({ position: buyPosition, price: t.price });
      } else if (t.trade_type === "sell") {
        if (openBuys.length > 0) {
          const matched = openBuys.pop()!;
          posMap.set(t.id, matched.position);
        }
        if (openBuys.length === 0) {
          buyPosition = 0;
        }
      }
    }
  }

  return posMap;
}
