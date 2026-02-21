"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import {
  listBots,
  updateBot,
  deleteBot,
  fetchBotStats,
  emergencySell,
  TradingBot,
  TradingBotUpdate,
  BotStats,
} from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import SimulationModal from "@/components/SimulationModal";

/** Parse a decimal string that may use comma as separator (French locale). */
const parseNum = (v: string) => parseFloat(v.replace(",", ".")) || 0;
const parseInt10 = (v: string) => parseInt(v.replace(",", ".")) || 10;

export default function BotDetailPage() {
  const router = useRouter();
  const params = useParams();
  const botId = Number(params.id);
  const { isAuthenticated, loading: authLoading } = useAuth();

  const [bot, setBot] = useState<TradingBot | null>(null);
  const [stats, setStats] = useState<BotStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Edit state
  const [editingBot, setEditingBot] = useState(false);
  const [editFormStr, setEditFormStr] = useState<Record<string, string>>({});
  const [editError, setEditError] = useState("");
  const [editSaving, setEditSaving] = useState(false);

  // Action loading states
  const [toggling, setToggling] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [confirmEmergencySell, setConfirmEmergencySell] = useState(false);
  const [emergencySelling, setEmergencySelling] = useState(false);
  const [simulatingBot, setSimulatingBot] = useState(false);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [authLoading, isAuthenticated, router]);

  useEffect(() => {
    if (authLoading || !isAuthenticated) return;
    Promise.all([listBots(), fetchBotStats()])
      .then(([botsData, statsData]) => {
        const found = botsData.find((b) => b.id === botId);
        if (!found) {
          setError("Bot not found");
          return;
        }
        setBot(found);
        const s = statsData.find((s) => s.bot_id === botId) ?? null;
        setStats(s);
      })
      .catch((err) => setError(err.message || "Failed to load bot"))
      .finally(() => setLoading(false));
  }, [authLoading, isAuthenticated, botId]);

  const handleToggle = async () => {
    if (!bot) return;
    setToggling(true);
    try {
      const newActive = bot.is_active ? 0 : 1;
      const updated = await updateBot(bot.id, { is_active: newActive });
      setBot(updated);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to toggle bot");
    } finally {
      setToggling(false);
    }
  };

  const handleDelete = async () => {
    if (!bot) return;
    setDeleting(true);
    try {
      await deleteBot(bot.id);
      router.push("/bots");
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to delete bot");
      setDeleting(false);
    }
  };

  const handleEmergencySell = async () => {
    if (!bot) return;
    setEmergencySelling(true);
    try {
      const result = await emergencySell(bot.id);
      alert(`Sold ${result.sold_count} position(s) at ${result.price}`);
      setBot({ ...bot, is_active: 0 });
      setConfirmEmergencySell(false);
      // Refresh stats
      const statsData = await fetchBotStats();
      const s = statsData.find((s) => s.bot_id === botId) ?? null;
      setStats(s);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Emergency sell failed");
    } finally {
      setEmergencySelling(false);
    }
  };

  const startEdit = () => {
    if (!bot) return;
    setEditingBot(true);
    setEditFormStr({
      min_price: String(bot.min_price),
      max_price: String(bot.max_price),
      total_amount: String(bot.total_amount),
      grid_levels: String(bot.grid_levels),
      sell_percentage: String(bot.sell_percentage),
    });
    setEditError("");
  };

  const cancelEdit = () => {
    setEditingBot(false);
    setEditFormStr({});
    setEditError("");
  };

  const handleEditSave = async () => {
    if (!bot) return;
    setEditError("");
    setEditSaving(true);
    try {
      const parsed: TradingBotUpdate = {
        min_price: parseNum(editFormStr.min_price),
        max_price: parseNum(editFormStr.max_price),
        total_amount: parseNum(editFormStr.total_amount),
        grid_levels: parseInt10(editFormStr.grid_levels),
        sell_percentage: parseNum(editFormStr.sell_percentage),
      };
      const updated = await updateBot(bot.id, parsed);
      setBot(updated);
      setEditingBot(false);
      setEditFormStr({});
    } catch (err) {
      setEditError(err instanceof Error ? err.message : "Failed to update bot");
    } finally {
      setEditSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-4rem)]">
        <p className="text-gray-500">Loading...</p>
      </div>
    );
  }

  if (error || !bot) {
    return (
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        <div className="text-center py-20 border border-gray-200 dark:border-gray-800 rounded-xl">
          <p className="text-red-500 text-lg mb-4">{error || "Bot not found"}</p>
          <Link
            href="/bots"
            className="px-6 py-2 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 transition"
          >
            Back to Bots
          </Link>
        </div>
      </div>
    );
  }

  const editInputClass =
    "w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900 focus:ring-2 focus:ring-blue-500 focus:border-transparent";

  // Compute P&L values
  const unrealized =
    stats && stats.open_positions_value !== null
      ? stats.open_positions_value - stats.open_positions_cost
      : null;
  const totalPnl =
    stats && unrealized !== null
      ? stats.realized_profit + unrealized
      : null;
  const monthlyPct =
    stats && bot.total_amount > 0
      ? (stats.monthly_realized_profit / bot.total_amount) * 100
      : null;

  // Grid step between two levels
  const gridStep =
    bot.grid_levels > 0 && bot.max_price > bot.min_price
      ? (bot.max_price - bot.min_price) / bot.grid_levels
      : null;
  const gridStepPct =
    gridStep !== null && bot.min_price > 0
      ? (gridStep / ((bot.max_price + bot.min_price) / 2)) * 100
      : null;

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      {/* Header */}
      <div className="mb-6">
        <Link
          href="/bots"
          className="text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
        >
          &larr; Back to Bots
        </Link>
      </div>

      <div className="flex justify-between items-center mb-8">
        <div className="flex items-center gap-3">
          <h1 className="text-3xl font-bold">{bot.symbol}</h1>
          <span
            className={`px-2 py-1 text-xs font-medium rounded-full ${
              bot.is_active
                ? "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400"
                : "bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400"
            }`}
          >
            {bot.is_active ? "Active" : "Inactive"}
          </span>
        </div>
      </div>

      {/* Monitoring - Stats */}
      {stats && (
        <div className="p-4 rounded-xl bg-gray-50 dark:bg-gray-900/50 space-y-2 text-sm mb-6 border border-gray-200 dark:border-gray-800">
          <h2 className="text-lg font-semibold mb-3">Monitoring</h2>
          <div className="flex justify-between">
            <span className="text-gray-500 dark:text-gray-400">Realized P&L</span>
            <span
              className={`font-medium ${
                stats.realized_profit >= 0
                  ? "text-green-600 dark:text-green-400"
                  : "text-red-600 dark:text-red-400"
              }`}
            >
              {stats.realized_profit >= 0 ? "+" : ""}
              {stats.realized_profit.toFixed(4)} $
            </span>
          </div>
          {stats.open_positions_count > 0 && (
            <>
              <div className="flex justify-between">
                <span className="text-gray-500 dark:text-gray-400">
                  Open ({stats.open_positions_count} pos)
                </span>
                <span className="font-medium">
                  {stats.open_positions_cost.toFixed(4)} $
                </span>
              </div>
              {stats.open_positions_value !== null && (
                <div className="flex justify-between">
                  <span className="text-gray-500 dark:text-gray-400">
                    Current Value
                  </span>
                  <span className="font-medium">
                    {stats.open_positions_value.toFixed(4)} $
                  </span>
                </div>
              )}
              {unrealized !== null && (
                <div className="flex justify-between">
                  <span className="text-gray-500 dark:text-gray-400">
                    Unrealized P&L
                  </span>
                  <span
                    className={`font-medium ${
                      unrealized >= 0
                        ? "text-green-600 dark:text-green-400"
                        : "text-red-600 dark:text-red-400"
                    }`}
                  >
                    {unrealized >= 0 ? "+" : ""}
                    {unrealized.toFixed(4)} $
                  </span>
                </div>
              )}
            </>
          )}
          {totalPnl !== null && (
            <div className="flex justify-between border-t border-gray-200 dark:border-gray-700 pt-2">
              <span className="text-gray-500 dark:text-gray-400 font-medium">
                Total P&L
              </span>
              <span
                className={`font-bold ${
                  totalPnl >= 0
                    ? "text-green-600 dark:text-green-400"
                    : "text-red-600 dark:text-red-400"
                }`}
              >
                {totalPnl >= 0 ? "+" : ""}
                {totalPnl.toFixed(4)} $
              </span>
            </div>
          )}
          {monthlyPct !== null && (
            <div className="flex justify-between">
              <span className="text-gray-500 dark:text-gray-400">
                Monthly P&L %
              </span>
              <span
                className={`font-medium ${
                  monthlyPct >= 0
                    ? "text-green-600 dark:text-green-400"
                    : "text-red-600 dark:text-red-400"
                }`}
              >
                {monthlyPct >= 0 ? "+" : ""}
                {monthlyPct.toFixed(2)}%
              </span>
            </div>
          )}
          {gridStep !== null && gridStepPct !== null && (
            <div className="flex justify-between border-t border-gray-200 dark:border-gray-700 pt-2">
              <span className="text-gray-500 dark:text-gray-400">
                Grid Step
              </span>
              <span className="font-medium">
                {gridStep.toFixed(4)} $ ({gridStepPct.toFixed(2)}%)
              </span>
            </div>
          )}
        </div>
      )}

      {/* Settings */}
      <div className="p-4 rounded-xl border border-gray-200 dark:border-gray-800 mb-6">
        <h2 className="text-lg font-semibold mb-3">Settings</h2>

        {editingBot ? (
          <div className="space-y-3">
            {editError && (
              <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 px-3 py-2 rounded-lg text-sm">
                {editError}
              </div>
            )}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">
                  Min Price ($)
                </label>
                <input
                  type="text"
                  inputMode="decimal"
                  value={editFormStr.min_price ?? ""}
                  onChange={(e) =>
                    setEditFormStr({ ...editFormStr, min_price: e.target.value })
                  }
                  className={editInputClass}
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">
                  Max Price ($)
                </label>
                <input
                  type="text"
                  inputMode="decimal"
                  value={editFormStr.max_price ?? ""}
                  onChange={(e) =>
                    setEditFormStr({ ...editFormStr, max_price: e.target.value })
                  }
                  className={editInputClass}
                />
              </div>
            </div>
            <div>
              <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">
                Amount ($)
              </label>
              <input
                type="text"
                inputMode="decimal"
                value={editFormStr.total_amount ?? ""}
                onChange={(e) =>
                  setEditFormStr({ ...editFormStr, total_amount: e.target.value })
                }
                className={editInputClass}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">
                  Grid Levels
                </label>
                <input
                  type="text"
                  inputMode="numeric"
                  value={editFormStr.grid_levels ?? ""}
                  onChange={(e) =>
                    setEditFormStr({ ...editFormStr, grid_levels: e.target.value })
                  }
                  className={editInputClass}
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">
                  Sell %
                </label>
                <input
                  type="text"
                  inputMode="decimal"
                  value={editFormStr.sell_percentage ?? ""}
                  onChange={(e) =>
                    setEditFormStr({
                      ...editFormStr,
                      sell_percentage: e.target.value,
                    })
                  }
                  className={editInputClass}
                />
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleEditSave}
                disabled={editSaving}
                className="flex-1 py-2 px-3 text-sm font-medium bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition disabled:opacity-50"
              >
                {editSaving ? "Saving..." : "Save"}
              </button>
              <button
                onClick={cancelEdit}
                className="flex-1 py-2 px-3 text-sm font-medium border border-gray-300 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div>
              <span className="text-gray-500 dark:text-gray-400">Min Price</span>
              <p className="font-medium">${bot.min_price.toLocaleString()}</p>
            </div>
            <div>
              <span className="text-gray-500 dark:text-gray-400">Max Price</span>
              <p className="font-medium">${bot.max_price.toLocaleString()}</p>
            </div>
            <div>
              <span className="text-gray-500 dark:text-gray-400">Amount</span>
              <p className="font-medium">${bot.total_amount.toLocaleString()}</p>
            </div>
            <div>
              <span className="text-gray-500 dark:text-gray-400">Grid Levels</span>
              <p className="font-medium">{bot.grid_levels}</p>
            </div>
            <div>
              <span className="text-gray-500 dark:text-gray-400">Sell %</span>
              <p className="font-medium">{bot.sell_percentage}%</p>
            </div>
          </div>
        )}
      </div>

      {/* Action Buttons */}
      <div className="space-y-3">
        <div className="flex gap-2">
          <button
            onClick={handleToggle}
            disabled={toggling}
            className={`flex-1 py-2 px-3 text-sm font-medium rounded-lg transition disabled:opacity-50 ${
              bot.is_active
                ? "bg-red-50 dark:bg-red-900/20 text-red-600 hover:bg-red-100 dark:hover:bg-red-900/40 border border-red-200 dark:border-red-800"
                : "bg-green-50 dark:bg-green-900/20 text-green-600 hover:bg-green-100 dark:hover:bg-green-900/40 border border-green-200 dark:border-green-800"
            }`}
          >
            {toggling ? "..." : bot.is_active ? "Stop" : "Start"}
          </button>
          <button
            onClick={startEdit}
            className="flex-1 py-2 px-3 text-sm font-medium border border-gray-300 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition"
          >
            Edit
          </button>
          {confirmDelete ? (
            <div className="flex gap-1">
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="py-2 px-3 text-sm font-medium bg-red-600 text-white rounded-lg hover:bg-red-700 transition disabled:opacity-50"
              >
                {deleting ? "..." : "Confirm"}
              </button>
              <button
                onClick={() => setConfirmDelete(false)}
                className="py-2 px-3 text-sm font-medium border border-gray-300 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition"
              >
                No
              </button>
            </div>
          ) : (
            <button
              onClick={() => setConfirmDelete(true)}
              className="py-2 px-3 text-sm font-medium text-red-500 hover:text-red-600 border border-gray-300 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition"
              title="Delete bot"
            >
              Delete
            </button>
          )}
        </div>

        <div className="flex gap-2">
          <Link
            href={`/trades?bot_id=${bot.id}`}
            className="flex-1 text-center px-4 py-2 text-sm font-medium text-blue-600 hover:text-blue-700 border border-blue-200 dark:border-blue-800 rounded-lg hover:bg-blue-50 dark:hover:bg-blue-900/20 transition"
          >
            Trades
          </Link>
          <Link
            href={`/bots/${bot.id}/chart`}
            className="flex-1 text-center px-4 py-2 text-sm font-medium text-indigo-600 hover:text-indigo-700 border border-indigo-200 dark:border-indigo-800 rounded-lg hover:bg-indigo-50 dark:hover:bg-indigo-900/20 transition"
          >
            Chart
          </Link>
          <button
            onClick={() => setSimulatingBot(true)}
            className="flex-1 text-center px-4 py-2 text-sm font-medium text-amber-600 hover:text-amber-700 border border-amber-200 dark:border-amber-800 rounded-lg hover:bg-amber-50 dark:hover:bg-amber-900/20 transition"
          >
            Simulate
          </button>
        </div>

        {stats && stats.open_positions_count > 0 &&
          (confirmEmergencySell ? (
            <div className="flex gap-2">
              <button
                onClick={handleEmergencySell}
                disabled={emergencySelling}
                className="flex-1 py-2 px-3 text-sm font-bold bg-orange-600 text-white rounded-lg hover:bg-orange-700 transition disabled:opacity-50"
              >
                {emergencySelling ? "Selling..." : "Confirm Sell All"}
              </button>
              <button
                onClick={() => setConfirmEmergencySell(false)}
                className="py-2 px-3 text-sm font-medium border border-gray-300 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition"
              >
                Cancel
              </button>
            </div>
          ) : (
            <button
              onClick={() => setConfirmEmergencySell(true)}
              className="w-full py-2 px-3 text-sm font-medium text-orange-600 hover:text-orange-700 border border-orange-300 dark:border-orange-800 rounded-lg hover:bg-orange-50 dark:hover:bg-orange-900/20 transition"
            >
              Emergency Sell All
            </button>
          ))}
      </div>

      {/* Simulation Modal */}
      {simulatingBot && (
        <SimulationModal
          bot={bot}
          onClose={() => setSimulatingBot(false)}
          onApply={(updated) => setBot(updated)}
        />
      )}
    </div>
  );
}
