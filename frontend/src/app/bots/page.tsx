"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  listBots,
  createBot,
  fetchUsdcSymbols,
  fetchBotStats,
  listLstmBots,
  createLstmBot,
  TradingBot,
  TradingBotCreate,
  BotStats,
  LstmBot,
  LstmBotCreate,
} from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

const emptyGridForm: TradingBotCreate = {
  symbol: "",
  min_price: 0,
  max_price: 0,
  total_amount: 0,
  grid_levels: 10,
  sell_percentage: 0,
};

const emptyLstmForm: LstmBotCreate = {
  symbol: "",
  timeframes: "15m,1d,1w",
  total_amount: 0,
  max_positions: 3,
  buy_slope_threshold: 0,
  sell_slope_threshold: 0,
  take_profit_pct: 2,
  stop_loss_pct: 3,
};

/** Parse a decimal string that may use comma as separator (French locale). */
const parseNum = (v: string) => parseFloat(v.replace(",", ".")) || 0;
const parseInt10 = (v: string) => parseInt(v.replace(",", ".")) || 10;

type BotType = "grid" | "lstm";

export default function BotsPage() {
  const router = useRouter();
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [bots, setBots] = useState<TradingBot[]>([]);
  const [lstmBots, setLstmBots] = useState<LstmBot[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [botType, setBotType] = useState<BotType>("grid");

  // Grid form state
  const [gridForm, setGridForm] = useState<TradingBotCreate>({ ...emptyGridForm });
  const [gridFormStr, setGridFormStr] = useState({
    min_price: "", max_price: "", total_amount: "", grid_levels: "10", sell_percentage: "",
  });

  // LSTM form state
  const [lstmForm, setLstmForm] = useState<LstmBotCreate>({ ...emptyLstmForm });
  const [lstmFormStr, setLstmFormStr] = useState({
    total_amount: "", max_positions: "3", buy_slope_threshold: "0",
    sell_slope_threshold: "0", take_profit_pct: "2", stop_loss_pct: "3", timeframes: "15m,1d,1w",
  });

  // Symbol picker
  const [symbols, setSymbols] = useState<string[]>([]);
  const [symbolsLoading, setSymbolsLoading] = useState(true);
  const [symbolSearch, setSymbolSearch] = useState("");
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Stats state
  const [statsMap, setStatsMap] = useState<Record<number, BotStats>>({});

  useEffect(() => {
    if (!authLoading && !isAuthenticated) router.push("/login");
  }, [authLoading, isAuthenticated, router]);

  useEffect(() => {
    fetchUsdcSymbols()
      .then(setSymbols)
      .catch(() => setSymbols([]))
      .finally(() => setSymbolsLoading(false));
  }, []);

  useEffect(() => {
    if (authLoading || !isAuthenticated) return;
    Promise.all([listBots(), fetchBotStats(), listLstmBots()])
      .then(([botsData, statsData, lstmData]) => {
        setBots(botsData);
        setLstmBots(lstmData);
        const map: Record<number, BotStats> = {};
        for (const s of statsData) map[s.bot_id] = s;
        setStatsMap(map);
      })
      .catch((err) => setError(err.message || "Failed to load bots"))
      .finally(() => setLoading(false));
  }, [authLoading, isAuthenticated, router]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const selectedSymbol = botType === "grid" ? gridForm.symbol : lstmForm.symbol;

  const selectSymbol = (sym: string) => {
    if (botType === "grid") {
      setGridForm({ ...gridForm, symbol: sym });
    } else {
      setLstmForm({ ...lstmForm, symbol: sym });
    }
    setSymbolSearch(sym);
    setDropdownOpen(false);
  };

  const clearSymbol = () => {
    if (botType === "grid") {
      setGridForm({ ...gridForm, symbol: "" });
    } else {
      setLstmForm({ ...lstmForm, symbol: "" });
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSaving(true);

    const symbol = botType === "grid" ? gridForm.symbol : lstmForm.symbol;
    if (!symbol) {
      setError("Please select a trading pair");
      setSaving(false);
      return;
    }

    try {
      if (botType === "grid") {
        const parsed: TradingBotCreate = {
          symbol: gridForm.symbol,
          min_price: parseNum(gridFormStr.min_price),
          max_price: parseNum(gridFormStr.max_price),
          total_amount: parseNum(gridFormStr.total_amount),
          grid_levels: parseInt10(gridFormStr.grid_levels),
          sell_percentage: parseNum(gridFormStr.sell_percentage),
        };
        const bot = await createBot(parsed);
        setBots((prev) => [bot, ...prev]);
        setGridForm({ ...emptyGridForm });
        setGridFormStr({ min_price: "", max_price: "", total_amount: "", grid_levels: "10", sell_percentage: "" });
      } else {
        const parsed: LstmBotCreate = {
          symbol: lstmForm.symbol,
          timeframes: lstmFormStr.timeframes,
          total_amount: parseNum(lstmFormStr.total_amount),
          max_positions: parseInt10(lstmFormStr.max_positions),
          buy_slope_threshold: parseNum(lstmFormStr.buy_slope_threshold),
          sell_slope_threshold: parseNum(lstmFormStr.sell_slope_threshold),
          take_profit_pct: parseNum(lstmFormStr.take_profit_pct),
          stop_loss_pct: parseNum(lstmFormStr.stop_loss_pct),
        };
        const bot = await createLstmBot(parsed);
        setLstmBots((prev) => [bot, ...prev]);
        setLstmForm({ ...emptyLstmForm });
        setLstmFormStr({
          total_amount: "", max_positions: "3", buy_slope_threshold: "0",
          sell_slope_threshold: "0", take_profit_pct: "2", stop_loss_pct: "3", timeframes: "15m,1d,1w",
        });
      }
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

  const tabClass = (active: boolean) =>
    `px-4 py-2 text-sm font-medium rounded-t-lg transition ${
      active
        ? "bg-white dark:bg-gray-900 border border-b-0 border-gray-200 dark:border-gray-700 text-emerald-600 dark:text-emerald-400"
        : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
    }`;

  const modelStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      ready: "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400",
      pending: "bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400",
      training: "bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400",
      error: "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400",
    };
    return colors[status] || colors.pending;
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold">Trading Bots</h1>
        <button
          onClick={() => { setShowForm(!showForm); setError(""); }}
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
          {/* Bot type tabs */}
          <div className="flex gap-1 -mb-1">
            <button type="button" className={tabClass(botType === "grid")} onClick={() => setBotType("grid")}>
              Grid Bot
            </button>
            <button type="button" className={tabClass(botType === "lstm")} onClick={() => setBotType("lstm")}>
              LSTM Bot
            </button>
          </div>

          <h2 className="text-lg font-semibold">
            {botType === "grid" ? "Create a Grid bot" : "Create an LSTM bot"}
          </h2>

          {error && (
            <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 px-4 py-3 rounded-lg">
              {error}
            </div>
          )}

          {/* Symbol picker (shared) */}
          <div ref={dropdownRef}>
            <label htmlFor="symbol" className="block text-sm font-medium mb-1">Symbol</label>
            <div className="relative">
              <input
                id="symbol"
                type="text"
                value={symbolSearch}
                onChange={(e) => {
                  setSymbolSearch(e.target.value.toUpperCase());
                  clearSymbol();
                  setDropdownOpen(true);
                }}
                onFocus={() => setDropdownOpen(true)}
                className={inputClass}
                placeholder={symbolsLoading ? "Loading pairs..." : "Search USDC pairs..."}
                disabled={symbolsLoading}
                autoComplete="off"
              />
              {selectedSymbol && (
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-green-600 dark:text-green-400">
                  {selectedSymbol}
                </span>
              )}
              {dropdownOpen && symbolSearch && (
                <ul className="absolute z-10 w-full mt-1 max-h-60 overflow-y-auto bg-white dark:bg-gray-900 border border-gray-300 dark:border-gray-700 rounded-lg shadow-lg">
                  {symbols.filter((s) => s.includes(symbolSearch)).slice(0, 50).map((sym) => (
                    <li
                      key={sym}
                      onClick={() => selectSymbol(sym)}
                      className="px-4 py-2 cursor-pointer hover:bg-blue-50 dark:hover:bg-gray-800 text-sm"
                    >
                      {sym}
                    </li>
                  ))}
                  {symbols.filter((s) => s.includes(symbolSearch)).length === 0 && (
                    <li className="px-4 py-3 text-sm text-gray-500">No matching USDC pairs found</li>
                  )}
                </ul>
              )}
            </div>
          </div>

          {/* ── Grid bot fields ── */}
          {botType === "grid" && (
            <>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label htmlFor="min_price" className="block text-sm font-medium mb-1">Min Price ($)</label>
                  <input id="min_price" type="text" inputMode="decimal" value={gridFormStr.min_price}
                    onChange={(e) => setGridFormStr({ ...gridFormStr, min_price: e.target.value })}
                    className={inputClass} required />
                </div>
                <div>
                  <label htmlFor="max_price" className="block text-sm font-medium mb-1">Max Price ($)</label>
                  <input id="max_price" type="text" inputMode="decimal" value={gridFormStr.max_price}
                    onChange={(e) => setGridFormStr({ ...gridFormStr, max_price: e.target.value })}
                    className={inputClass} required />
                </div>
              </div>
              <div>
                <label htmlFor="total_amount" className="block text-sm font-medium mb-1">Total Amount ($)</label>
                <input id="total_amount" type="text" inputMode="decimal" value={gridFormStr.total_amount}
                  onChange={(e) => setGridFormStr({ ...gridFormStr, total_amount: e.target.value })}
                  className={inputClass} required />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label htmlFor="grid_levels" className="block text-sm font-medium mb-1">Grid Levels</label>
                  <input id="grid_levels" type="text" inputMode="numeric" value={gridFormStr.grid_levels}
                    onChange={(e) => setGridFormStr({ ...gridFormStr, grid_levels: e.target.value })}
                    className={inputClass} required />
                </div>
                <div>
                  <label htmlFor="sell_percentage" className="block text-sm font-medium mb-1">Sell Percentage (%)</label>
                  <input id="sell_percentage" type="text" inputMode="decimal" value={gridFormStr.sell_percentage}
                    onChange={(e) => setGridFormStr({ ...gridFormStr, sell_percentage: e.target.value })}
                    className={inputClass} required />
                </div>
              </div>
            </>
          )}

          {/* ── LSTM bot fields ── */}
          {botType === "lstm" && (
            <>
              <div>
                <label htmlFor="timeframes" className="block text-sm font-medium mb-1">Timeframes</label>
                <input id="timeframes" type="text" value={lstmFormStr.timeframes}
                  onChange={(e) => setLstmFormStr({ ...lstmFormStr, timeframes: e.target.value })}
                  className={inputClass} placeholder="15m,1d,1w" required />
                <p className="text-xs text-gray-500 mt-1">Comma-separated: short, medium, long (e.g. 15m,1d,1w)</p>
              </div>
              <div>
                <label htmlFor="lstm_total_amount" className="block text-sm font-medium mb-1">Total Amount ($)</label>
                <input id="lstm_total_amount" type="text" inputMode="decimal" value={lstmFormStr.total_amount}
                  onChange={(e) => setLstmFormStr({ ...lstmFormStr, total_amount: e.target.value })}
                  className={inputClass} required />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label htmlFor="take_profit_pct" className="block text-sm font-medium mb-1">Take Profit (%)</label>
                  <input id="take_profit_pct" type="text" inputMode="decimal" value={lstmFormStr.take_profit_pct}
                    onChange={(e) => setLstmFormStr({ ...lstmFormStr, take_profit_pct: e.target.value })}
                    className={inputClass} required />
                </div>
                <div>
                  <label htmlFor="stop_loss_pct" className="block text-sm font-medium mb-1">Stop Loss (%)</label>
                  <input id="stop_loss_pct" type="text" inputMode="decimal" value={lstmFormStr.stop_loss_pct}
                    onChange={(e) => setLstmFormStr({ ...lstmFormStr, stop_loss_pct: e.target.value })}
                    className={inputClass} required />
                </div>
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label htmlFor="max_positions" className="block text-sm font-medium mb-1">Max Positions</label>
                  <input id="max_positions" type="text" inputMode="numeric" value={lstmFormStr.max_positions}
                    onChange={(e) => setLstmFormStr({ ...lstmFormStr, max_positions: e.target.value })}
                    className={inputClass} required />
                </div>
                <div>
                  <label htmlFor="buy_slope" className="block text-sm font-medium mb-1">Buy Slope Threshold</label>
                  <input id="buy_slope" type="text" inputMode="decimal" value={lstmFormStr.buy_slope_threshold}
                    onChange={(e) => setLstmFormStr({ ...lstmFormStr, buy_slope_threshold: e.target.value })}
                    className={inputClass} required />
                </div>
                <div>
                  <label htmlFor="sell_slope" className="block text-sm font-medium mb-1">Sell Slope Threshold</label>
                  <input id="sell_slope" type="text" inputMode="decimal" value={lstmFormStr.sell_slope_threshold}
                    onChange={(e) => setLstmFormStr({ ...lstmFormStr, sell_slope_threshold: e.target.value })}
                    className={inputClass} required />
                </div>
              </div>
            </>
          )}

          <button
            type="submit"
            disabled={saving}
            className="w-full py-3 px-4 bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-medium rounded-lg hover:from-emerald-600 hover:to-teal-700 transition disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-emerald-500/25"
          >
            {saving ? "Creating..." : `Create ${botType === "grid" ? "Grid" : "LSTM"} Bot`}
          </button>
        </form>
      )}

      {bots.length === 0 && lstmBots.length === 0 && !showForm ? (
        <div className="text-center py-20 border border-gray-200 dark:border-gray-800 rounded-xl">
          <p className="text-gray-500 dark:text-gray-400 text-lg mb-4">No trading bots configured yet.</p>
          <button
            onClick={() => setShowForm(true)}
            className="px-6 py-2 bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-medium rounded-lg hover:from-emerald-600 hover:to-teal-700 transition shadow-lg shadow-emerald-500/25"
          >
            Create your first bot
          </button>
        </div>
      ) : (
        <>
          {/* ── Grid bots section ── */}
          {bots.length > 0 && (
            <>
              <h2 className="text-xl font-semibold mb-4">Grid Bots</h2>
              {/* Mobile: cards */}
              <div className="sm:hidden space-y-3 mb-8">
                {bots.map((bot) => {
                  const s = statsMap[bot.id];
                  const unrealized = s && s.open_positions_value !== null ? s.open_positions_value - s.open_positions_cost : null;
                  const totalPnl = s && unrealized !== null ? s.realized_profit + unrealized : s ? s.realized_profit : null;
                  const monthlyPnl = s && unrealized !== null ? s.monthly_realized_profit + unrealized : s ? s.monthly_realized_profit : null;
                  const monthlyPct = monthlyPnl !== null && s && s.monthly_buy_cost > 0 ? (monthlyPnl / s.monthly_buy_cost) * 100 : null;
                  return (
                    <div key={bot.id} className="border border-gray-200 dark:border-gray-800 rounded-xl p-4 space-y-3">
                      <div className="flex items-center justify-between">
                        <Link href={`/bots/${bot.id}`} className="text-base font-semibold text-blue-600 dark:text-blue-400">{bot.symbol}</Link>
                        <span className={`px-2 py-1 text-xs font-medium rounded-full ${bot.is_active ? "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400" : "bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400"}`}>
                          {bot.is_active ? "Active" : "Inactive"}
                        </span>
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-sm">
                        <div>
                          <p className="text-gray-500 dark:text-gray-400 text-xs mb-0.5">Total P&L</p>
                          {totalPnl !== null ? (
                            <span className={`font-medium ${totalPnl >= 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}>
                              {totalPnl >= 0 ? "+" : ""}{totalPnl.toFixed(2)} $
                            </span>
                          ) : <span className="text-gray-400">&mdash;</span>}
                        </div>
                        <div>
                          <p className="text-gray-500 dark:text-gray-400 text-xs mb-0.5">Monthly P&L %</p>
                          {monthlyPct !== null ? (
                            <span className={`font-medium ${monthlyPct >= 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}>
                              {monthlyPct >= 0 ? "+" : ""}{monthlyPct.toFixed(2)}%
                            </span>
                          ) : <span className="text-gray-400">&mdash;</span>}
                        </div>
                      </div>
                      <Link href={`/bots/${bot.id}/chart`}
                        className="flex items-center justify-center gap-1 py-1.5 text-xs font-medium bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 rounded-lg hover:bg-indigo-500/30 transition">
                        Chart
                      </Link>
                    </div>
                  );
                })}
              </div>
              {/* Desktop: table */}
              <div className="hidden sm:block border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden mb-8">
                <table className="w-full text-sm">
                  <thead className="bg-gradient-to-r from-gray-50 to-gray-100 dark:from-gray-900/50 dark:to-gray-800/30">
                    <tr>
                      <th className="px-4 py-3 text-left font-medium text-gray-500 dark:text-gray-400">Symbol</th>
                      <th className="px-4 py-3 text-right font-medium text-gray-500 dark:text-gray-400">Amount</th>
                      <th className="px-4 py-3 text-right font-medium text-gray-500 dark:text-gray-400">Total P&L</th>
                      <th className="px-4 py-3 text-center font-medium text-gray-500 dark:text-gray-400">Chart</th>
                      <th className="px-4 py-3 text-right font-medium text-gray-500 dark:text-gray-400">Monthly P&L</th>
                      <th className="px-4 py-3 text-center font-medium text-gray-500 dark:text-gray-400">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 dark:divide-gray-800">
                    {bots.map((bot) => {
                      const s = statsMap[bot.id];
                      const unrealized = s && s.open_positions_value !== null ? s.open_positions_value - s.open_positions_cost : null;
                      const totalPnl = s && unrealized !== null ? s.realized_profit + unrealized : s ? s.realized_profit : null;
                      const monthlyPnl = s && unrealized !== null ? s.monthly_realized_profit + unrealized : s ? s.monthly_realized_profit : null;
                      const monthlyPct = monthlyPnl !== null && s && s.monthly_buy_cost > 0 ? (monthlyPnl / s.monthly_buy_cost) * 100 : null;
                      return (
                        <tr key={bot.id} className="hover:bg-gray-50 dark:hover:bg-gray-900/30">
                          <td className="px-4 py-3 font-medium">
                            <Link href={`/bots/${bot.id}`} className="text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 hover:underline">{bot.symbol}</Link>
                          </td>
                          <td className="px-4 py-3 text-right font-medium">{bot.total_amount} $</td>
                          <td className="px-4 py-3 text-right">
                            {totalPnl !== null ? (
                              <span className={`font-medium ${totalPnl >= 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}>
                                {totalPnl >= 0 ? "+" : ""}{totalPnl.toFixed(2)} $
                              </span>
                            ) : <span className="text-gray-400">&mdash;</span>}
                          </td>
                          <td className="px-4 py-3 text-center">
                            <Link href={`/bots/${bot.id}/chart`}
                              className="inline-flex items-center px-3 py-1 text-xs font-medium bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 rounded-lg hover:bg-indigo-500/30 transition">
                              Chart
                            </Link>
                          </td>
                          <td className="px-4 py-3 text-right">
                            {monthlyPct !== null ? (
                              <span className={`font-medium ${monthlyPct >= 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}>
                                {monthlyPct >= 0 ? "+" : ""}{monthlyPct.toFixed(2)}%
                              </span>
                            ) : <span className="text-gray-400">&mdash;</span>}
                          </td>
                          <td className="px-4 py-3 text-center">
                            <span className={`px-2 py-1 text-xs font-medium rounded-full ${bot.is_active ? "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400" : "bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400"}`}>
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

          {/* ── LSTM bots section ── */}
          {lstmBots.length > 0 && (
            <>
              <h2 className="text-xl font-semibold mb-4">LSTM Bots</h2>
              {/* Mobile: cards */}
              <div className="sm:hidden space-y-3 mb-8">
                {lstmBots.map((bot) => (
                  <div key={bot.id} className="border border-gray-200 dark:border-gray-800 rounded-xl p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <Link href={`/lstm-bots/${bot.id}`} className="text-base font-semibold text-blue-600 dark:text-blue-400">{bot.symbol}</Link>
                      <div className="flex gap-2">
                        <span className={`px-2 py-1 text-xs font-medium rounded-full ${modelStatusBadge(bot.model_status)}`}>
                          {bot.model_status}
                        </span>
                        <span className={`px-2 py-1 text-xs font-medium rounded-full ${bot.is_active ? "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400" : "bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400"}`}>
                          {bot.is_active ? "Active" : "Inactive"}
                        </span>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div>
                        <p className="text-gray-500 dark:text-gray-400 text-xs mb-0.5">Amount</p>
                        <span className="font-medium">{bot.total_amount} $</span>
                      </div>
                      <div>
                        <p className="text-gray-500 dark:text-gray-400 text-xs mb-0.5">Timeframes</p>
                        <span className="font-medium">{bot.timeframes}</span>
                      </div>
                      <div>
                        <p className="text-gray-500 dark:text-gray-400 text-xs mb-0.5">TP / SL</p>
                        <span className="font-medium">{bot.take_profit_pct}% / {bot.stop_loss_pct}%</span>
                      </div>
                      <div>
                        <p className="text-gray-500 dark:text-gray-400 text-xs mb-0.5">Max Positions</p>
                        <span className="font-medium">{bot.max_positions}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              {/* Desktop: table */}
              <div className="hidden sm:block border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden mb-8">
                <table className="w-full text-sm">
                  <thead className="bg-gradient-to-r from-gray-50 to-gray-100 dark:from-gray-900/50 dark:to-gray-800/30">
                    <tr>
                      <th className="px-4 py-3 text-left font-medium text-gray-500 dark:text-gray-400">Symbol</th>
                      <th className="px-4 py-3 text-center font-medium text-gray-500 dark:text-gray-400">Timeframes</th>
                      <th className="px-4 py-3 text-right font-medium text-gray-500 dark:text-gray-400">Amount</th>
                      <th className="px-4 py-3 text-center font-medium text-gray-500 dark:text-gray-400">TP / SL</th>
                      <th className="px-4 py-3 text-center font-medium text-gray-500 dark:text-gray-400">Model</th>
                      <th className="px-4 py-3 text-center font-medium text-gray-500 dark:text-gray-400">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 dark:divide-gray-800">
                    {lstmBots.map((bot) => (
                      <tr key={bot.id} className="hover:bg-gray-50 dark:hover:bg-gray-900/30">
                        <td className="px-4 py-3 font-medium">
                          <Link href={`/lstm-bots/${bot.id}`} className="text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 hover:underline">{bot.symbol}</Link>
                        </td>
                        <td className="px-4 py-3 text-center text-gray-600 dark:text-gray-400">{bot.timeframes}</td>
                        <td className="px-4 py-3 text-right font-medium">{bot.total_amount} $</td>
                        <td className="px-4 py-3 text-center">{bot.take_profit_pct}% / {bot.stop_loss_pct}%</td>
                        <td className="px-4 py-3 text-center">
                          <span className={`px-2 py-1 text-xs font-medium rounded-full ${modelStatusBadge(bot.model_status)}`}>
                            {bot.model_status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-center">
                          <span className={`px-2 py-1 text-xs font-medium rounded-full ${bot.is_active ? "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400" : "bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400"}`}>
                            {bot.is_active ? "Active" : "Inactive"}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
