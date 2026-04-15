"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { listDeletedBots, type DeletedBot } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

export default function HistoryPage() {
  const router = useRouter();
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [bots, setBots] = useState<DeletedBot[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) router.push("/login");
  }, [authLoading, isAuthenticated, router]);

  useEffect(() => {
    if (authLoading || !isAuthenticated) return;
    listDeletedBots()
      .then(setBots)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [authLoading, isAuthenticated]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-4rem)]">
        <p className="text-gray-500">Loading...</p>
      </div>
    );
  }

  const totalPnl = bots.reduce((s, b) => s + b.total_pnl, 0);

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <h1 className="text-3xl font-bold mb-2">History</h1>
      <p className="text-gray-500 text-sm mb-8">
        Archived bots &middot; Total P&L:{" "}
        <span className={`font-medium ${totalPnl >= 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}>
          {totalPnl >= 0 ? "+" : ""}{totalPnl.toFixed(2)} $
        </span>
      </p>

      {bots.length === 0 ? (
        <p className="text-gray-400 text-center py-20">No deleted bots yet.</p>
      ) : (
        <div className="space-y-4">
          {bots.map((bot) => {
            const pnlPct = bot.total_amount > 0 ? (bot.total_pnl / bot.total_amount) * 100 : 0;
            const createdDate = new Date(bot.created_at);
            const deletedDate = new Date(bot.deleted_at);
            const days = Math.max(1, Math.floor((deletedDate.getTime() - createdDate.getTime()) / 86400000));

            return (
              <div
                key={bot.id}
                className="p-5 rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900/30"
              >
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-lg font-semibold">{bot.symbol}</h2>
                  <span className={`text-lg font-bold ${bot.total_pnl >= 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}>
                    {bot.total_pnl >= 0 ? "+" : ""}{bot.total_pnl.toFixed(2)} $
                    <span className="text-sm font-medium ml-1">
                      ({pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(2)}%)
                    </span>
                  </span>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
                  <div>
                    <p className="text-gray-400 text-xs">Grid</p>
                    <p className="font-medium">{bot.min_price} – {bot.max_price}</p>
                  </div>
                  <div>
                    <p className="text-gray-400 text-xs">Levels / Sell %</p>
                    <p className="font-medium">{bot.grid_levels} / {bot.sell_percentage}%</p>
                  </div>
                  <div>
                    <p className="text-gray-400 text-xs">Amount</p>
                    <p className="font-medium">{bot.total_amount} $</p>
                  </div>
                  <div>
                    <p className="text-gray-400 text-xs">Duration</p>
                    <p className="font-medium">{days} days</p>
                  </div>
                </div>

                <div className="flex gap-4 mt-3 text-xs text-gray-400">
                  <span>Created: {createdDate.toLocaleDateString()}</span>
                  <span>Deleted: {deletedDate.toLocaleDateString()}</span>
                  <span>Realized: {bot.realized_pnl >= 0 ? "+" : ""}{bot.realized_pnl.toFixed(2)} $</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
