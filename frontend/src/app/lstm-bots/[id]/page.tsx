"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import {
  listLstmBots,
  updateLstmBot,
  deleteLstmBot,
  fetchLstmSlopes,
  refreshLstmModelStatus,
  LstmBot,
  LstmBotUpdate,
  SlopeInfo,
} from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

const parseNum = (v: string) => parseFloat(v.replace(",", ".")) || 0;
const parseInt10 = (v: string) => parseInt(v.replace(",", ".")) || 0;

export default function LstmBotDetailPage() {
  const router = useRouter();
  const params = useParams();
  const botId = Number(params.id);
  const { isAuthenticated, loading: authLoading } = useAuth();

  const [bot, setBot] = useState<LstmBot | null>(null);
  const [slopes, setSlopes] = useState<SlopeInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Edit state
  const [editing, setEditing] = useState(false);
  const [editFormStr, setEditFormStr] = useState<Record<string, string>>({});
  const [editError, setEditError] = useState("");
  const [editSaving, setEditSaving] = useState(false);

  // Action states
  const [toggling, setToggling] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);

  const showToast = (message: string, type: "success" | "error" = "success") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  };

  useEffect(() => {
    if (!authLoading && !isAuthenticated) router.push("/login");
  }, [authLoading, isAuthenticated, router]);

  useEffect(() => {
    if (authLoading || !isAuthenticated) return;
    listLstmBots()
      .then((bots) => {
        const found = bots.find((b) => b.id === botId);
        if (!found) {
          setError("LSTM Bot not found");
          return;
        }
        setBot(found);
        // Fetch slopes if model is ready
        if (found.model_status === "ready") {
          fetchLstmSlopes(found.id)
            .then(setSlopes)
            .catch(() => {});
        }
      })
      .catch((err) => setError(err.message || "Failed to load bot"))
      .finally(() => setLoading(false));
  }, [authLoading, isAuthenticated, botId]);

  const handleToggle = async () => {
    if (!bot) return;
    setToggling(true);
    try {
      const updated = await updateLstmBot(bot.id, { is_active: bot.is_active ? 0 : 1 });
      setBot(updated);
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Failed to toggle bot", "error");
    } finally {
      setToggling(false);
    }
  };

  const handleDelete = async () => {
    if (!bot) return;
    setDeleting(true);
    try {
      await deleteLstmBot(bot.id);
      router.push("/bots");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Failed to delete bot", "error");
      setDeleting(false);
    }
  };

  const handleRefreshStatus = async () => {
    if (!bot) return;
    setRefreshing(true);
    try {
      const updated = await refreshLstmModelStatus(bot.id);
      setBot(updated);
      if (updated.model_status === "ready") {
        showToast("Model is ready!");
        fetchLstmSlopes(updated.id).then(setSlopes).catch(() => {});
      } else {
        showToast(`Model status: ${updated.model_status}`, "error");
      }
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Failed to refresh status", "error");
    } finally {
      setRefreshing(false);
    }
  };

  const startEdit = () => {
    if (!bot) return;
    setEditing(true);
    setEditFormStr({
      timeframes: bot.timeframes,
      total_amount: String(bot.total_amount),
      max_positions: String(bot.max_positions),
      buy_slope_threshold: String(bot.buy_slope_threshold),
      sell_slope_threshold: String(bot.sell_slope_threshold),
      take_profit_pct: String(bot.take_profit_pct),
      stop_loss_pct: String(bot.stop_loss_pct),
    });
    setEditError("");
  };

  const cancelEdit = () => {
    setEditing(false);
    setEditFormStr({});
    setEditError("");
  };

  const handleEditSave = async () => {
    if (!bot) return;
    setEditError("");
    setEditSaving(true);
    try {
      const parsed: LstmBotUpdate = {
        timeframes: editFormStr.timeframes,
        total_amount: parseNum(editFormStr.total_amount),
        max_positions: parseInt10(editFormStr.max_positions),
        buy_slope_threshold: parseNum(editFormStr.buy_slope_threshold),
        sell_slope_threshold: parseNum(editFormStr.sell_slope_threshold),
        take_profit_pct: parseNum(editFormStr.take_profit_pct),
        stop_loss_pct: parseNum(editFormStr.stop_loss_pct),
      };
      const updated = await updateLstmBot(bot.id, parsed);
      setBot(updated);
      setEditing(false);
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
          <Link href="/bots" className="px-6 py-2 bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-medium rounded-lg hover:from-emerald-600 hover:to-teal-700 transition">
            Back to Bots
          </Link>
        </div>
      </div>
    );
  }

  const editInputClass =
    "w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900 focus:ring-2 focus:ring-emerald-500 focus:border-transparent";

  const modelStatusColors: Record<string, string> = {
    ready: "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400",
    pending: "bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400",
    training: "bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400",
    error: "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400",
  };

  const slopeDirectionColors: Record<string, string> = {
    up: "text-green-600 dark:text-green-400",
    down: "text-red-600 dark:text-red-400",
    neutral: "text-gray-500 dark:text-gray-400",
  };

  const slopeArrow: Record<string, string> = {
    up: "\u2191",
    down: "\u2193",
    neutral: "\u2192",
  };

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      {/* Toast */}
      {toast && (
        <div className={`fixed bottom-6 right-6 z-50 flex items-center gap-3 px-5 py-3 rounded-xl shadow-lg text-white text-sm font-medium ${
          toast.type === "success" ? "bg-emerald-600" : "bg-red-600"
        }`}>
          <span>{toast.type === "success" ? "\u2713" : "\u2715"}</span>
          {toast.message}
        </div>
      )}

      {/* Header */}
      <div className="mb-6">
        <Link href="/bots" className="text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300">
          &larr; Back to Bots
        </Link>
      </div>

      <div className="flex justify-between items-center mb-8">
        <div className="flex items-center gap-3">
          <h1 className="text-3xl font-bold">{bot.symbol}</h1>
          <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400">
            LSTM
          </span>
          <span className={`px-2 py-1 text-xs font-medium rounded-full ${
            bot.is_active
              ? "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400"
              : "bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400"
          }`}>
            {bot.is_active ? "Active" : "Inactive"}
          </span>
        </div>
      </div>

      {/* Slope predictions */}
      {bot.model_status === "ready" && slopes.length > 0 && (
        <div className="p-4 rounded-xl bg-gradient-to-br from-purple-500/5 to-indigo-500/5 border border-purple-500/20 mb-6">
          <h2 className="text-lg font-semibold mb-3 text-purple-700 dark:text-purple-400">Slope Predictions</h2>
          <div className="grid grid-cols-3 gap-4">
            {slopes.map((s) => (
              <div key={s.timeframe} className="text-center">
                <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">{s.timeframe}</p>
                <p className={`text-2xl font-bold ${slopeDirectionColors[s.direction]}`}>
                  {slopeArrow[s.direction]}
                </p>
                <p className={`text-sm font-medium ${slopeDirectionColors[s.direction]}`}>
                  {s.slope >= 0 ? "+" : ""}{s.slope.toFixed(4)}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Model status */}
      <div className="p-4 rounded-xl bg-gradient-to-br from-emerald-500/5 to-teal-500/5 border border-emerald-500/20 mb-6">
        <h2 className="text-lg font-semibold mb-3 text-emerald-700 dark:text-emerald-400">Model</h2>
        <div className="flex justify-between items-center text-sm">
          <span className="text-gray-500 dark:text-gray-400">Status</span>
          <span className={`px-3 py-1 text-xs font-medium rounded-full ${modelStatusColors[bot.model_status] || modelStatusColors.pending}`}>
            {bot.model_status}
          </span>
        </div>
        <div className="flex justify-between text-sm mt-2">
          <span className="text-gray-500 dark:text-gray-400">Timeframes</span>
          <span className="font-medium">{bot.timeframes}</span>
        </div>
        {bot.model_status !== "ready" && (
          <div className="mt-3 p-3 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800">
            <p className="text-sm text-amber-700 dark:text-amber-400 mb-2">
              Model is not ready. Train the model first, then click refresh.
            </p>
            <button
              onClick={handleRefreshStatus}
              disabled={refreshing}
              className="px-4 py-1.5 text-sm font-medium bg-amber-600 text-white rounded-lg hover:bg-amber-700 transition disabled:opacity-50"
            >
              {refreshing ? "Checking..." : "Refresh Status"}
            </button>
          </div>
        )}
      </div>

      {/* Settings */}
      <div className="p-4 rounded-xl bg-gradient-to-br from-blue-500/5 to-indigo-500/5 border border-blue-500/20 mb-6">
        <h2 className="text-lg font-semibold mb-3 text-blue-700 dark:text-blue-400">Settings</h2>

        {editing ? (
          <div className="space-y-3">
            {editError && (
              <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 px-3 py-2 rounded-lg text-sm">
                {editError}
              </div>
            )}
            <div>
              <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Timeframes</label>
              <input type="text" value={editFormStr.timeframes ?? ""} onChange={(e) => setEditFormStr({ ...editFormStr, timeframes: e.target.value })} className={editInputClass} />
            </div>
            <div>
              <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Amount ($)</label>
              <input type="text" inputMode="decimal" value={editFormStr.total_amount ?? ""} onChange={(e) => setEditFormStr({ ...editFormStr, total_amount: e.target.value })} className={editInputClass} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Take Profit (%)</label>
                <input type="text" inputMode="decimal" value={editFormStr.take_profit_pct ?? ""} onChange={(e) => setEditFormStr({ ...editFormStr, take_profit_pct: e.target.value })} className={editInputClass} />
              </div>
              <div>
                <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Stop Loss (%)</label>
                <input type="text" inputMode="decimal" value={editFormStr.stop_loss_pct ?? ""} onChange={(e) => setEditFormStr({ ...editFormStr, stop_loss_pct: e.target.value })} className={editInputClass} />
              </div>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Max Positions</label>
                <input type="text" inputMode="numeric" value={editFormStr.max_positions ?? ""} onChange={(e) => setEditFormStr({ ...editFormStr, max_positions: e.target.value })} className={editInputClass} />
              </div>
              <div>
                <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Buy Slope</label>
                <input type="text" inputMode="decimal" value={editFormStr.buy_slope_threshold ?? ""} onChange={(e) => setEditFormStr({ ...editFormStr, buy_slope_threshold: e.target.value })} className={editInputClass} />
              </div>
              <div>
                <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Sell Slope</label>
                <input type="text" inputMode="decimal" value={editFormStr.sell_slope_threshold ?? ""} onChange={(e) => setEditFormStr({ ...editFormStr, sell_slope_threshold: e.target.value })} className={editInputClass} />
              </div>
            </div>
            <div className="flex gap-2">
              <button onClick={handleEditSave} disabled={editSaving}
                className="flex-1 py-2 px-3 text-sm font-medium bg-gradient-to-r from-emerald-500 to-teal-600 text-white rounded-lg hover:from-emerald-600 hover:to-teal-700 transition disabled:opacity-50">
                {editSaving ? "Saving..." : "Save"}
              </button>
              <button onClick={cancelEdit}
                className="flex-1 py-2 px-3 text-sm font-medium border border-gray-300 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition">
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div>
              <span className="text-gray-500 dark:text-gray-400">Amount</span>
              <p className="font-medium">${bot.total_amount.toLocaleString()}</p>
            </div>
            <div>
              <span className="text-gray-500 dark:text-gray-400">Max Positions</span>
              <p className="font-medium">{bot.max_positions}</p>
            </div>
            <div>
              <span className="text-gray-500 dark:text-gray-400">Take Profit</span>
              <p className="font-medium">{bot.take_profit_pct}%</p>
            </div>
            <div>
              <span className="text-gray-500 dark:text-gray-400">Stop Loss</span>
              <p className="font-medium">{bot.stop_loss_pct}%</p>
            </div>
            <div>
              <span className="text-gray-500 dark:text-gray-400">Buy Slope Threshold</span>
              <p className="font-medium">{bot.buy_slope_threshold}</p>
            </div>
            <div>
              <span className="text-gray-500 dark:text-gray-400">Sell Slope Threshold</span>
              <p className="font-medium">{bot.sell_slope_threshold}</p>
            </div>
          </div>
        )}
      </div>

      {/* Action Buttons */}
      <div className="space-y-3">
        <div className="flex gap-2 mb-2">
          <Link
            href={`/lstm-bots/${bot.id}/chart`}
            className="flex-1 text-center px-4 py-2 text-sm font-medium bg-purple-500/20 text-purple-400 border border-purple-500/30 rounded-lg hover:bg-purple-500/30 transition"
          >
            Chart
          </Link>
        </div>
        <div className="flex gap-2">
          <button onClick={handleToggle} disabled={toggling || bot.model_status !== "ready"}
            className={`flex-1 py-2 px-3 text-sm font-medium rounded-lg transition disabled:opacity-50 ${
              bot.is_active
                ? "bg-red-50 dark:bg-red-900/20 text-red-600 hover:bg-red-100 dark:hover:bg-red-900/40 border border-red-200 dark:border-red-800"
                : "bg-green-50 dark:bg-green-900/20 text-green-600 hover:bg-green-100 dark:hover:bg-green-900/40 border border-green-200 dark:border-green-800"
            }`}
            title={bot.model_status !== "ready" ? "Model must be ready to start" : undefined}
          >
            {toggling ? "..." : bot.is_active ? "Stop" : "Start"}
          </button>
          <button onClick={startEdit}
            className="flex-1 py-2 px-3 text-sm font-medium border border-gray-300 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition">
            Edit
          </button>
          {confirmDelete ? (
            <div className="flex gap-1">
              <button onClick={handleDelete} disabled={deleting}
                className="py-2 px-3 text-sm font-medium bg-red-600 text-white rounded-lg hover:bg-red-700 transition disabled:opacity-50">
                {deleting ? "..." : "Confirm"}
              </button>
              <button onClick={() => setConfirmDelete(false)}
                className="py-2 px-3 text-sm font-medium border border-gray-300 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition">
                No
              </button>
            </div>
          ) : (
            <button onClick={() => setConfirmDelete(true)}
              className="py-2 px-3 text-sm font-medium text-red-500 hover:text-red-600 border border-gray-300 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition"
              title="Delete bot">
              Delete
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
