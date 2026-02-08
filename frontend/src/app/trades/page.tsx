"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { fetchAllTrades, fetchBotTrades, listBots, Trade, TradingBot } from "@/lib/api";

export default function TradesPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const botId = searchParams.get("bot_id");

  const [trades, setTrades] = useState<Trade[]>([]);
  const [bots, setBots] = useState<TradingBot[]>([]);
  const [loading, setLoading] = useState(true);

  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;

  useEffect(() => {
    if (!token) {
      router.push("/login");
      return;
    }

    const load = async () => {
      try {
        const botsList = await listBots(token);
        setBots(botsList);

        let tradesList: Trade[];
        if (botId) {
          tradesList = await fetchBotTrades(token, parseInt(botId));
          const bot = botsList.find((b) => b.id === parseInt(botId));
          if (bot) {
            tradesList = tradesList.map((t) => ({ ...t, symbol: bot.symbol }));
          }
        } else {
          tradesList = await fetchAllTrades(token);
        }
        setTrades(tradesList);
      } catch {
        router.push("/login");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [token, router, botId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-4rem)]">
        <p className="text-gray-500">Loading...</p>
      </div>
    );
  }

  // Build a map of bot_id -> symbol for display
  const botMap = Object.fromEntries(bots.map((b) => [b.id, b.symbol]));

  // Compute drop percentage from previous buy for each trade
  const tradesWithDrop = computeDropFromPreviousBuy(trades, botMap);

  const selectedBot = botId ? bots.find((b) => b.id === parseInt(botId)) : null;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold">Trades</h1>
          {selectedBot && (
            <p className="text-gray-500 mt-1">
              Filtered by bot: <span className="font-medium">{selectedBot.symbol}</span>
              {" "}
              <Link href="/trades" className="text-blue-600 hover:underline text-sm">
                (show all)
              </Link>
            </p>
          )}
        </div>
      </div>

      {tradesWithDrop.length === 0 ? (
        <div className="text-center py-20 border border-gray-200 dark:border-gray-800 rounded-xl">
          <p className="text-gray-500 dark:text-gray-400 text-lg">
            No trades yet.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 dark:border-gray-800 text-left">
                <th className="py-3 px-4 font-medium text-gray-500">Date</th>
                <th className="py-3 px-4 font-medium text-gray-500">Symbol</th>
                <th className="py-3 px-4 font-medium text-gray-500">Type</th>
                <th className="py-3 px-4 font-medium text-gray-500 text-right">Price</th>
                <th className="py-3 px-4 font-medium text-gray-500 text-right">Quantity</th>
                <th className="py-3 px-4 font-medium text-gray-500 text-right">Drop %</th>
              </tr>
            </thead>
            <tbody>
              {tradesWithDrop.map((t) => (
                <tr
                  key={t.id}
                  className="border-b border-gray-100 dark:border-gray-900 hover:bg-gray-50 dark:hover:bg-gray-900/50"
                >
                  <td className="py-3 px-4 text-gray-600 dark:text-gray-400">
                    {new Date(t.created_at).toLocaleString()}
                  </td>
                  <td className="py-3 px-4 font-medium">{t.symbol || botMap[t.trading_bot_id] || "—"}</td>
                  <td className="py-3 px-4">
                    <span
                      className={`px-2 py-1 text-xs font-medium rounded-full ${
                        t.trade_type === "buy"
                          ? "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400"
                          : "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400"
                      }`}
                    >
                      {t.trade_type.toUpperCase()}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right font-mono">{t.price.toFixed(8)}</td>
                  <td className="py-3 px-4 text-right font-mono">{t.quantity.toFixed(6)}</td>
                  <td className="py-3 px-4 text-right font-mono">
                    {t.dropLabel}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

interface TradeWithDrop extends Trade {
  dropLabel: string;
}

function computeDropFromPreviousBuy(trades: Trade[], botMap: Record<number, string>): TradeWithDrop[] {
  // Trades are sorted desc (newest first). We process per bot_id in chronological order.
  const byBot: Record<number, Trade[]> = {};
  for (const t of trades) {
    if (!byBot[t.trading_bot_id]) byBot[t.trading_bot_id] = [];
    byBot[t.trading_bot_id].push(t);
  }

  const dropMap = new Map<number, string>();

  for (const botId of Object.keys(byBot)) {
    const botTrades = byBot[parseInt(botId)].slice().reverse(); // chronological
    let lastBuyPrice: number | null = null;

    for (const t of botTrades) {
      if (t.trade_type === "buy") {
        if (lastBuyPrice === null) {
          dropMap.set(t.id, "1st buy");
        } else {
          const drop = ((lastBuyPrice - t.price) / lastBuyPrice) * 100;
          dropMap.set(t.id, `-${drop.toFixed(2)}%`);
        }
        lastBuyPrice = t.price;
      } else {
        dropMap.set(t.id, "—");
      }
    }
  }

  return trades.map((t) => ({
    ...t,
    dropLabel: dropMap.get(t.id) || "—",
  }));
}
