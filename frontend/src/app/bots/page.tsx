"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  listBots,
  createBot,
  updateBot,
  deleteBot,
  fetchUsdcSymbols,
  fetchBotStats,
  emergencySell,
  TradingBot,
  TradingBotCreate,
  TradingBotUpdate,
  BotStats,
} from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import SimulationModal from "@/components/SimulationModal";

const emptyForm: TradingBotCreate = {
  symbol: "",
  min_price: 0,
  max_price: 0,
  total_amount: 0,
  grid_levels: 10,
  sell_percentage: 0,
};

/** Parse a decimal string that may use comma as separator (French locale). */
const parseNum = (v: string) => parseFloat(v.replace(",", ".")) || 0;
const parseInt10 = (v: string) => parseInt(v.replace(",", ".")) || 10;

export default function BotsPage() {
  const router = useRouter();
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [bots, setBots] = useState<TradingBot[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState<TradingBotCreate>({ ...emptyForm });
  const [formStr, setFormStr] = useState({ min_price: "", max_price: "", total_amount: "", grid_levels: "10", sell_percentage: "" });
  const [symbols, setSymbols] = useState<string[]>([]);
  const [symbolsLoading, setSymbolsLoading] = useState(true);
  const [symbolSearch, setSymbolSearch] = useState("");
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Stats state
  const [statsMap, setStatsMap] = useState<Record<number, BotStats>>({});

  // Edit state
  const [editingBotId, setEditingBotId] = useState<number | null>(null);
  const [editFormStr, setEditFormStr] = useState<Record<string, string>>({});
  const [editError, setEditError] = useState("");
  const [editSaving, setEditSaving] = useState(false);

  // Toggle/delete/emergency-sell loading state
  const [togglingBotId, setTogglingBotId] = useState<number | null>(null);
  const [deletingBotId, setDeletingBotId] = useState<number | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);
  const [confirmEmergencySellId, setConfirmEmergencySellId] = useState<number | null>(null);
  const [emergencySellingBotId, setEmergencySellingBotId] = useState<number | null>(null);
  const [simulatingBotId, setSimulatingBotId] = useState<number | null>(null);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [authLoading, isAuthenticated, router]);

  useEffect(() => {
    fetchUsdcSymbols()
      .then(setSymbols)
      .catch(() => setSymbols([]))
      .finally(() => setSymbolsLoading(false));
  }, []);

  useEffect(() => {
    if (authLoading || !isAuthenticated) return;
    Promise.all([listBots(), fetchBotStats()])
      .then(([botsData, statsData]) => {
        setBots(botsData);
        const map: Record<number, BotStats> = {};
        for (const s of statsData) map[s.bot_id] = s;
        setStatsMap(map);
      })
      .catch((err) => setError(err.message || "Failed to load bots"))
      .finally(() => setLoading(false));
  }, [authLoading, isAuthenticated, router]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node)
      ) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSaving(true);

    if (!form.symbol) {
      setError("Please select a trading pair");
      setSaving(false);
      return;
    }

    try {
      const parsed: TradingBotCreate = {
        symbol: form.symbol,
        min_price: parseNum(formStr.min_price),
        max_price: parseNum(formStr.max_price),
        total_amount: parseNum(formStr.total_amount),
        grid_levels: parseInt10(formStr.grid_levels),
        sell_percentage: parseNum(formStr.sell_percentage),
      };
      const bot = await createBot(parsed);
      setBots((prev) => [bot, ...prev]);
      setForm({ ...emptyForm });
      setFormStr({ min_price: "", max_price: "", total_amount: "", grid_levels: "10", sell_percentage: "" });
      setSymbolSearch("");
      setShowForm(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create bot");
    } finally {
      setSaving(false);
    }
  };

  const handleToggle = async (bot: TradingBot) => {
    setTogglingBotId(bot.id);
    try {
      const newActive = bot.is_active ? 0 : 1;
      const updated = await updateBot(bot.id, { is_active: newActive });
      setBots((prev) => prev.map((b) => (b.id === updated.id ? updated : b)));
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to toggle bot");
    } finally {
      setTogglingBotId(null);
    }
  };

  const handleDelete = async (botId: number) => {
    setDeletingBotId(botId);
    try {
      await deleteBot(botId);
      setBots((prev) => prev.filter((b) => b.id !== botId));
      setConfirmDeleteId(null);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to delete bot");
    } finally {
      setDeletingBotId(null);
    }
  };

  const handleEmergencySell = async (botId: number) => {
    setEmergencySellingBotId(botId);
    try {
      const result = await emergencySell(botId);
      alert(`Sold ${result.sold_count} position(s) at ${result.price}`);
      setBots((prev) => prev.map((b) => (b.id === botId ? { ...b, is_active: 0 } : b)));
      setConfirmEmergencySellId(null);
      // Refresh stats
      const statsData = await fetchBotStats();
      const map: Record<number, BotStats> = {};
      for (const s of statsData) map[s.bot_id] = s;
      setStatsMap(map);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Emergency sell failed");
    } finally {
      setEmergencySellingBotId(null);
    }
  };

  const startEdit = (bot: TradingBot) => {
    setEditingBotId(bot.id);
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
    setEditingBotId(null);

    setEditFormStr({});
    setEditError("");
  };

  const handleEditSave = async (botId: number) => {
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
      const updated = await updateBot(botId, parsed);
      setBots((prev) => prev.map((b) => (b.id === updated.id ? updated : b)));
      setEditingBotId(null);
  
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

  const inputClass =
    "w-full px-4 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900 focus:ring-2 focus:ring-blue-500 focus:border-transparent";

  const editInputClass =
    "w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900 focus:ring-2 focus:ring-blue-500 focus:border-transparent";

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold">Trading Bots</h1>
        <button
          onClick={() => {
            setShowForm(!showForm);
            setError("");
          }}
          className="px-4 py-2 text-sm font-medium bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
        >
          {showForm ? "Cancel" : "+ New Bot"}
        </button>
      </div>

      {showForm && (
        <form
          onSubmit={handleCreate}
          className="mb-8 p-6 border border-gray-200 dark:border-gray-800 rounded-xl space-y-4"
        >
          <h2 className="text-lg font-semibold">Create a new bot</h2>

          {error && (
            <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 px-4 py-3 rounded-lg">
              {error}
            </div>
          )}

          <div ref={dropdownRef}>
            <label htmlFor="symbol" className="block text-sm font-medium mb-1">
              Symbol
            </label>
            <div className="relative">
              <input
                id="symbol"
                type="text"
                value={symbolSearch}
                onChange={(e) => {
                  setSymbolSearch(e.target.value.toUpperCase());
                  setForm({ ...form, symbol: "" });
                  setDropdownOpen(true);
                }}
                onFocus={() => setDropdownOpen(true)}
                className={inputClass}
                placeholder={
                  symbolsLoading ? "Loading pairs..." : "Search USDC pairs..."
                }
                disabled={symbolsLoading}
                autoComplete="off"
              />
              {form.symbol && (
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-green-600 dark:text-green-400">
                  {form.symbol}
                </span>
              )}
              {dropdownOpen && symbolSearch && (
                <ul className="absolute z-10 w-full mt-1 max-h-60 overflow-y-auto bg-white dark:bg-gray-900 border border-gray-300 dark:border-gray-700 rounded-lg shadow-lg">
                  {symbols
                    .filter((s) => s.includes(symbolSearch))
                    .slice(0, 50)
                    .map((sym) => (
                      <li
                        key={sym}
                        onClick={() => {
                          setForm({ ...form, symbol: sym });
                          setSymbolSearch(sym);
                          setDropdownOpen(false);
                        }}
                        className="px-4 py-2 cursor-pointer hover:bg-blue-50 dark:hover:bg-gray-800 text-sm"
                      >
                        {sym}
                      </li>
                    ))}
                  {symbols.filter((s) => s.includes(symbolSearch)).length ===
                    0 && (
                    <li className="px-4 py-3 text-sm text-gray-500">
                      No matching USDC pairs found
                    </li>
                  )}
                </ul>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label
                htmlFor="min_price"
                className="block text-sm font-medium mb-1"
              >
                Min Price ($)
              </label>
              <input
                id="min_price"
                type="text"
                inputMode="decimal"
                value={formStr.min_price}
                onChange={(e) =>
                  setFormStr({ ...formStr, min_price: e.target.value })
                }
                className={inputClass}
                required
              />
            </div>
            <div>
              <label
                htmlFor="max_price"
                className="block text-sm font-medium mb-1"
              >
                Max Price ($)
              </label>
              <input
                id="max_price"
                type="text"
                inputMode="decimal"
                value={formStr.max_price}
                onChange={(e) =>
                  setFormStr({ ...formStr, max_price: e.target.value })
                }
                className={inputClass}
                required
              />
            </div>
          </div>

          <div>
            <label
              htmlFor="total_amount"
              className="block text-sm font-medium mb-1"
            >
              Total Amount ($)
            </label>
            <input
              id="total_amount"
              type="text"
              inputMode="decimal"
              value={formStr.total_amount}
              onChange={(e) =>
                setFormStr({ ...formStr, total_amount: e.target.value })
              }
              className={inputClass}
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label
                htmlFor="grid_levels"
                className="block text-sm font-medium mb-1"
              >
                Grid Levels
              </label>
              <input
                id="grid_levels"
                type="text"
                inputMode="numeric"
                value={formStr.grid_levels}
                onChange={(e) =>
                  setFormStr({ ...formStr, grid_levels: e.target.value })
                }
                className={inputClass}
                required
              />
            </div>
            <div>
              <label
                htmlFor="sell_percentage"
                className="block text-sm font-medium mb-1"
              >
                Sell Percentage (%)
              </label>
              <input
                id="sell_percentage"
                type="text"
                inputMode="decimal"
                value={formStr.sell_percentage}
                onChange={(e) =>
                  setFormStr({ ...formStr, sell_percentage: e.target.value })
                }
                className={inputClass}
                required
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={saving}
            className="w-full py-3 px-4 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? "Creating..." : "Create Bot"}
          </button>
        </form>
      )}

      {bots.length === 0 && !showForm ? (
        <div className="text-center py-20 border border-gray-200 dark:border-gray-800 rounded-xl">
          <p className="text-gray-500 dark:text-gray-400 text-lg mb-4">
            No trading bots configured yet.
          </p>
          <button
            onClick={() => setShowForm(true)}
            className="px-6 py-2 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 transition"
          >
            Create your first bot
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {bots.map((bot) => (
            <div
              key={bot.id}
              className="p-6 border border-gray-200 dark:border-gray-800 rounded-xl space-y-3"
            >
              <div className="flex justify-between items-center">
                <h2 className="text-xl font-bold">{bot.symbol}</h2>
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

              {editingBotId === bot.id ? (
                /* ─── Edit Mode ─── */
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
                          setEditFormStr({ ...editFormStr, sell_percentage: e.target.value })
                        }
                        className={editInputClass}
                      />
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleEditSave(bot.id)}
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
                /* ─── View Mode ─── */
                <>
                  {/* ─── Stats ─── */}
                  {statsMap[bot.id] && (() => {
                    const s = statsMap[bot.id];
                    const unrealized = s.open_positions_value !== null
                      ? s.open_positions_value - s.open_positions_cost
                      : null;
                    const totalPnl = unrealized !== null
                      ? s.realized_profit + unrealized
                      : null;
                    return (
                      <div className="p-3 rounded-lg bg-gray-50 dark:bg-gray-900/50 space-y-2 text-sm">
                        <div className="flex justify-between">
                          <span className="text-gray-500 dark:text-gray-400">Realized P&L</span>
                          <span className={`font-medium ${s.realized_profit >= 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}>
                            {s.realized_profit >= 0 ? "+" : ""}{s.realized_profit.toFixed(4)} $
                          </span>
                        </div>
                        {s.open_positions_count > 0 && (
                          <>
                            <div className="flex justify-between">
                              <span className="text-gray-500 dark:text-gray-400">Open ({s.open_positions_count} pos)</span>
                              <span className="font-medium">{s.open_positions_cost.toFixed(4)} $</span>
                            </div>
                            {s.open_positions_value !== null && (
                              <div className="flex justify-between">
                                <span className="text-gray-500 dark:text-gray-400">Current Value</span>
                                <span className="font-medium">{s.open_positions_value.toFixed(4)} $</span>
                              </div>
                            )}
                            {unrealized !== null && (
                              <div className="flex justify-between">
                                <span className="text-gray-500 dark:text-gray-400">Unrealized P&L</span>
                                <span className={`font-medium ${unrealized >= 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}>
                                  {unrealized >= 0 ? "+" : ""}{unrealized.toFixed(4)} $
                                </span>
                              </div>
                            )}
                          </>
                        )}
                        {totalPnl !== null && (
                          <div className="flex justify-between border-t border-gray-200 dark:border-gray-700 pt-2">
                            <span className="text-gray-500 dark:text-gray-400 font-medium">Total P&L</span>
                            <span className={`font-bold ${totalPnl >= 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}>
                              {totalPnl >= 0 ? "+" : ""}{totalPnl.toFixed(4)} $
                            </span>
                          </div>
                        )}
                        {bot.total_amount > 0 && (() => {
                          const monthlyPct = (s.monthly_realized_profit / bot.total_amount) * 100;
                          return (
                            <div className="flex justify-between">
                              <span className="text-gray-500 dark:text-gray-400">Monthly P&L %</span>
                              <span className={`font-medium ${monthlyPct >= 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}>
                                {monthlyPct >= 0 ? "+" : ""}{monthlyPct.toFixed(2)}%
                              </span>
                            </div>
                          );
                        })()}
                      </div>
                    );
                  })()}

                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div>
                      <span className="text-gray-500 dark:text-gray-400">
                        Min Price
                      </span>
                      <p className="font-medium">
                        ${bot.min_price.toLocaleString()}
                      </p>
                    </div>
                    <div>
                      <span className="text-gray-500 dark:text-gray-400">
                        Max Price
                      </span>
                      <p className="font-medium">
                        ${bot.max_price.toLocaleString()}
                      </p>
                    </div>
                    <div>
                      <span className="text-gray-500 dark:text-gray-400">
                        Amount
                      </span>
                      <p className="font-medium">
                        ${bot.total_amount.toLocaleString()}
                      </p>
                    </div>
                    <div>
                      <span className="text-gray-500 dark:text-gray-400">
                        Grid Levels
                      </span>
                      <p className="font-medium">{bot.grid_levels}</p>
                    </div>
                    <div>
                      <span className="text-gray-500 dark:text-gray-400">
                        Sell %
                      </span>
                      <p className="font-medium">{bot.sell_percentage}%</p>
                    </div>
                  </div>

                  <div className="flex gap-2">
                    <button
                      onClick={() => handleToggle(bot)}
                      disabled={togglingBotId === bot.id}
                      className={`flex-1 py-2 px-3 text-sm font-medium rounded-lg transition disabled:opacity-50 ${
                        bot.is_active
                          ? "bg-red-50 dark:bg-red-900/20 text-red-600 hover:bg-red-100 dark:hover:bg-red-900/40 border border-red-200 dark:border-red-800"
                          : "bg-green-50 dark:bg-green-900/20 text-green-600 hover:bg-green-100 dark:hover:bg-green-900/40 border border-green-200 dark:border-green-800"
                      }`}
                    >
                      {togglingBotId === bot.id
                        ? "..."
                        : bot.is_active
                          ? "Stop"
                          : "Start"}
                    </button>
                    <button
                      onClick={() => startEdit(bot)}
                      className="flex-1 py-2 px-3 text-sm font-medium border border-gray-300 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition"
                    >
                      Edit
                    </button>
                    {confirmDeleteId === bot.id ? (
                      <div className="flex gap-1">
                        <button
                          onClick={() => handleDelete(bot.id)}
                          disabled={deletingBotId === bot.id}
                          className="py-2 px-3 text-sm font-medium bg-red-600 text-white rounded-lg hover:bg-red-700 transition disabled:opacity-50"
                        >
                          {deletingBotId === bot.id ? "..." : "Confirm"}
                        </button>
                        <button
                          onClick={() => setConfirmDeleteId(null)}
                          className="py-2 px-3 text-sm font-medium border border-gray-300 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition"
                        >
                          No
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setConfirmDeleteId(bot.id)}
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
                      onClick={() => setSimulatingBotId(bot.id)}
                      className="flex-1 text-center px-4 py-2 text-sm font-medium text-amber-600 hover:text-amber-700 border border-amber-200 dark:border-amber-800 rounded-lg hover:bg-amber-50 dark:hover:bg-amber-900/20 transition"
                    >
                      Simulate
                    </button>
                  </div>

                  {statsMap[bot.id] && statsMap[bot.id].open_positions_count > 0 && (
                    confirmEmergencySellId === bot.id ? (
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleEmergencySell(bot.id)}
                          disabled={emergencySellingBotId === bot.id}
                          className="flex-1 py-2 px-3 text-sm font-bold bg-orange-600 text-white rounded-lg hover:bg-orange-700 transition disabled:opacity-50"
                        >
                          {emergencySellingBotId === bot.id ? "Selling..." : "Confirm Sell All"}
                        </button>
                        <button
                          onClick={() => setConfirmEmergencySellId(null)}
                          className="py-2 px-3 text-sm font-medium border border-gray-300 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setConfirmEmergencySellId(bot.id)}
                        className="w-full py-2 px-3 text-sm font-medium text-orange-600 hover:text-orange-700 border border-orange-300 dark:border-orange-800 rounded-lg hover:bg-orange-50 dark:hover:bg-orange-900/20 transition"
                      >
                        Emergency Sell All
                      </button>
                    )
                  )}
                </>
              )}
            </div>
          ))}
        </div>
      )}

      {simulatingBotId !== null && (() => {
        const simBot = bots.find((b) => b.id === simulatingBotId);
        if (!simBot) return null;
        return (
          <SimulationModal
            bot={simBot}
            onClose={() => setSimulatingBotId(null)}
            onApply={(updated) => {
              setBots((prev) => prev.map((b) => (b.id === updated.id ? updated : b)));
            }}
          />
        );
      })()}
    </div>
  );
}
