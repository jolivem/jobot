"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  listBots,
  createBot,
  fetchUsdcSymbols,
  fetchBotStats,
  TradingBot,
  TradingBotCreate,
  BotStats,
} from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

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

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-4rem)]">
        <p className="text-gray-500">Loading...</p>
      </div>
    );
  }

  const inputClass =
    "w-full px-4 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900 focus:ring-2 focus:ring-emerald-500 focus:border-transparent";

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold">Trading Bots</h1>
        <button
          onClick={() => {
            setShowForm(!showForm);
            setError("");
          }}
          className="px-4 py-2 text-sm font-medium bg-gradient-to-r from-emerald-500 to-teal-600 text-white rounded-lg hover:from-emerald-600 hover:to-teal-700 transition shadow-lg shadow-emerald-500/25"
        >
          {showForm ? "Cancel" : "+ New Bot"}
        </button>
      </div>

      {showForm && (
        <form
          onSubmit={handleCreate}
          className="mb-8 p-6 rounded-xl bg-gradient-to-br from-gray-50 to-gray-100/50 dark:from-gray-900/50 dark:to-gray-800/30 border border-gray-200 dark:border-gray-800 space-y-4"
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
            className="w-full py-3 px-4 bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-medium rounded-lg hover:from-emerald-600 hover:to-teal-700 transition disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-emerald-500/25"
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
            className="px-6 py-2 bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-medium rounded-lg hover:from-emerald-600 hover:to-teal-700 transition shadow-lg shadow-emerald-500/25"
          >
            Create your first bot
          </button>
        </div>
      ) : (
        <>
          {/* Mobile: cards */}
          <div className="sm:hidden space-y-3">
            {bots.map((bot) => {
              const s = statsMap[bot.id];
              const unrealized =
                s && s.open_positions_value !== null
                  ? s.open_positions_value - s.open_positions_cost
                  : null;
              const totalPnl =
                s && unrealized !== null
                  ? s.realized_profit + unrealized
                  : s ? s.realized_profit : null;
              const totalPct =
                totalPnl !== null && bot.total_amount > 0
                  ? (totalPnl / bot.total_amount) * 100
                  : null;
              const daysSinceCreation = bot.created_at
                ? Math.max(1, Math.floor((Date.now() - new Date(bot.created_at).getTime()) / 86400000))
                : null;

              return (
                <div key={bot.id} className="border border-gray-200 dark:border-gray-800 rounded-xl p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <Link
                      href={`/bots/${bot.id}`}
                      className="text-base font-semibold text-blue-600 dark:text-blue-400"
                    >
                      {bot.symbol}
                    </Link>
                    <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                      bot.is_active
                        ? "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400"
                        : "bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400"
                    }`}>
                      {bot.is_active ? "Active" : "Inactive"}
                    </span>
                  </div>
                  <div className="text-sm">
                    <p className="text-gray-500 dark:text-gray-400 text-xs mb-0.5">Total P&L</p>
                    {totalPnl !== null ? (
                      <div>
                        <span className={`font-medium ${totalPnl >= 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}>
                          {totalPnl >= 0 ? "+" : ""}{totalPnl.toFixed(2)} $
                        </span>
                        <span className="text-xs text-gray-400 ml-1">
                          {totalPct !== null && <span>{totalPct >= 0 ? "+" : ""}{totalPct.toFixed(2)}%</span>}
                          {daysSinceCreation !== null && <span> / {daysSinceCreation}d</span>}
                        </span>
                      </div>
                    ) : <span className="text-gray-400">—</span>}
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-gray-500 dark:text-gray-400 text-xs mb-0.5">Range</p>
                      {(() => {
                        const cp = s?.current_price;
                        if (cp == null) return <span className="text-gray-400">—</span>;
                        if (cp > bot.max_price) return <span className="font-medium text-orange-500">Above</span>;
                        if (cp < bot.min_price) return <span className="font-medium text-blue-500">Below</span>;
                        return <span className="font-medium text-green-600 dark:text-green-400">Inside</span>;
                      })()}
                    </div>
                    <Link
                      href={`/bots/${bot.id}/chart`}
                      className="inline-flex items-center px-3 py-1.5 text-xs font-medium bg-purple-100 dark:bg-purple-900/20 text-purple-600 dark:text-purple-300 rounded-lg hover:bg-purple-200 dark:hover:bg-purple-900/40 transition"
                    >
                      Chart
                    </Link>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Desktop: table */}
          <div className="hidden sm:block border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gradient-to-r from-gray-50 to-gray-100 dark:from-gray-900/50 dark:to-gray-800/30">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-gray-500 dark:text-gray-400">Symbol</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-500 dark:text-gray-400">Amount</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-500 dark:text-gray-400">Total P&L</th>
                  <th className="px-4 py-3 text-center font-medium text-gray-500 dark:text-gray-400">Range</th>
                  <th className="px-4 py-3 text-center font-medium text-gray-500 dark:text-gray-400">Chart</th>
                  <th className="px-4 py-3 text-center font-medium text-gray-500 dark:text-gray-400">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-800">
                {bots.map((bot) => {
                  const s = statsMap[bot.id];
                  const unrealized =
                    s && s.open_positions_value !== null
                      ? s.open_positions_value - s.open_positions_cost
                      : null;
                  const totalPnl =
                    s && unrealized !== null
                      ? s.realized_profit + unrealized
                      : s ? s.realized_profit : null;
                  const totalPct =
                    totalPnl !== null && bot.total_amount > 0
                      ? (totalPnl / bot.total_amount) * 100
                      : null;
                  const daysSinceCreation = bot.created_at
                    ? Math.max(1, Math.floor((Date.now() - new Date(bot.created_at).getTime()) / 86400000))
                    : null;

                  return (
                    <tr key={bot.id} className="hover:bg-gray-50 dark:hover:bg-gray-900/30">
                      <td className="px-4 py-3 font-medium">
                        <Link
                          href={`/bots/${bot.id}`}
                          className="text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 hover:underline"
                        >
                          {bot.symbol}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-right font-medium">
                        {bot.total_amount} $
                      </td>
                      <td className="px-4 py-3 text-right">
                        {totalPnl !== null ? (
                          <div>
                            <span className={`font-medium ${totalPnl >= 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}>
                              {totalPnl >= 0 ? "+" : ""}{totalPnl.toFixed(2)} $
                            </span>
                            <div className="text-xs text-gray-400">
                              {totalPct !== null && <span>{totalPct >= 0 ? "+" : ""}{totalPct.toFixed(2)}%</span>}
                              {daysSinceCreation !== null && <span> / {daysSinceCreation}d</span>}
                            </div>
                          </div>
                        ) : <span className="text-gray-400">—</span>}
                      </td>
                      <td className="px-4 py-3 text-center">
                        {(() => {
                          const cp = s?.current_price;
                          if (cp == null) return <span className="text-gray-400">—</span>;
                          if (cp > bot.max_price) return <span className="font-medium text-orange-500">Above</span>;
                          if (cp < bot.min_price) return <span className="font-medium text-blue-500">Below</span>;
                          return <span className="font-medium text-green-600 dark:text-green-400">Inside</span>;
                        })()}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <Link
                          href={`/bots/${bot.id}/chart`}
                          className="inline-flex items-center px-3 py-1 text-xs font-medium bg-purple-100 dark:bg-purple-900/20 text-purple-600 dark:text-purple-300 rounded-lg hover:bg-purple-200 dark:hover:bg-purple-900/40 transition"
                        >
                          Chart
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                          bot.is_active
                            ? "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400"
                            : "bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400"
                        }`}>
                          {bot.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
