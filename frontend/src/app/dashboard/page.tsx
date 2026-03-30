"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import {
  fetchBnbBalance,
  fetchPrice,
  convertToBnb,
  fetchProfitHistory,
  fetchPnlSnapshots,
  fetchBotStats,
  listBots,
  fetchHealth,
  type ProfitPoint,
  type BotStats,
  type TradingBot,
  type HealthStatus,
} from "@/lib/api";
import {
  createChart,
  HistogramSeries,
  LineSeries,
  ColorType,
  type IChartApi,
  type UTCTimestamp,
} from "lightweight-charts";

export default function DashboardPage() {
  const router = useRouter();
  const { user, isAuthenticated, loading } = useAuth();

  const [bnbFree, setBnbFree] = useState<number | null>(null);
  const [bnbLocked, setBnbLocked] = useState<number | null>(null);
  const [bnbPrice, setBnbPrice] = useState<number | null>(null);
  const [bnbLoading, setBnbLoading] = useState(false);
  const [usdcFree, setUsdcFree] = useState<number | null>(null);

  const [convertAmount, setConvertAmount] = useState("");
  const [converting, setConverting] = useState(false);
  const [convertResult, setConvertResult] = useState<string | null>(null);
  const [convertError, setConvertError] = useState<string | null>(null);

  const [profitData, setProfitData] = useState<ProfitPoint[]>([]);
  const [profitRange, setProfitRange] = useState<"1m" | "6m" | "all">("all");
  const [pnlData, setPnlData] = useState<ProfitPoint[]>([]);
  const [pnlRange, setPnlRange] = useState<"24h" | "7d" | "30d">("7d");
  const [stats, setStats] = useState<BotStats[]>([]);
  const [bots, setBots] = useState<TradingBot[]>([]);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const pnlChartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!loading && !isAuthenticated) router.push("/login");
  }, [loading, isAuthenticated, router]);

  useEffect(() => {
    if (user?.binance_api_key) {
      setBnbLoading(true);
      Promise.all([fetchBnbBalance(), fetchPrice("BNBUSDC")])
        .then(([data, price]) => {
          setBnbFree(data.free);
          setBnbLocked(data.locked);
          setBnbPrice(price);
          setUsdcFree(data.usdc_free ?? null);
        })
        .catch(() => {
          setBnbFree(null);
          setBnbLocked(null);
          setUsdcFree(null);
        })
        .finally(() => setBnbLoading(false));
    }
  }, [user]);

  useEffect(() => {
    if (loading || !isAuthenticated) return;
    Promise.all([fetchProfitHistory(), fetchBotStats(), listBots(), fetchPnlSnapshots(30)])
      .then(([profit, statsData, botsData, pnl]) => {
        setProfitData(profit);
        setStats(statsData);
        setBots(botsData);
        setPnlData(pnl);
      })
      .catch(() => {});
    fetchHealth().then(setHealth).catch(() => setHealth(null));
  }, [loading, isAuthenticated]);

  // Computed totals
  const totalRealized = stats.reduce((s, b) => s + b.realized_profit, 0);
  const totalOpenCost = stats.reduce((s, b) => s + b.open_positions_cost, 0);
  const totalOpenValue = stats.reduce(
    (s, b) => s + (b.open_positions_value ?? 0),
    0
  );
  const totalUnrealized = totalOpenValue - totalOpenCost;
  const totalPnl = totalRealized + totalUnrealized;
  const activeBots = bots.filter((b) => b.is_active).length;
  const totalPositions = stats.reduce((s, b) => s + b.open_positions_count, 0);
  const bestDay = profitData.length
    ? Math.max(...profitData.map((p) => p.value))
    : 0;
  const today = new Date().toISOString().slice(0, 10);
  const todayProfit =
    profitData.find((p) => p.time === today)?.value ?? 0;

  // Filter profit data by selected range
  const filteredProfitData = (() => {
    if (profitRange === "all") return profitData;
    const now = new Date();
    const cutoff = new Date(now);
    if (profitRange === "1m") cutoff.setMonth(cutoff.getMonth() - 1);
    else cutoff.setMonth(cutoff.getMonth() - 6);
    const cutoffStr = cutoff.toISOString().slice(0, 10);
    return profitData.filter((p) => p.time >= cutoffStr);
  })();

  // Render chart
  useEffect(() => {
    if (!chartContainerRef.current || filteredProfitData.length === 0) return;

    const isDark = document.documentElement.classList.contains("dark");
    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: 300,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: isDark ? "#9ca3af" : "#6b7280",
      },
      grid: {
        vertLines: { color: isDark ? "#1f2937" : "#e5e7eb" },
        horzLines: { color: isDark ? "#1f2937" : "#e5e7eb" },
      },
      rightPriceScale: {
        borderColor: isDark ? "#374151" : "#d1d5db",
      },
      timeScale: {
        borderColor: isDark ? "#374151" : "#d1d5db",
      },
      crosshair: { mode: 0 },
    });

    const series = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "price", precision: 2, minMove: 0.01 },
    });

    const data = filteredProfitData.map((p) => ({
      time: p.time as unknown as UTCTimestamp,
      value: p.value,
      color: p.value >= 0 ? "#22c55e" : "#ef4444",
    }));

    series.setData(data);
    chart.timeScale().fitContent();
    chartRef.current = chart;

    const resizeObserver = new ResizeObserver(() => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    });
    resizeObserver.observe(chartContainerRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, [filteredProfitData]);

  // Filter P&L snapshots by selected range
  const filteredPnlData = (() => {
    if (pnlData.length === 0) return [];
    const now = new Date();
    const cutoff = new Date(now);
    if (pnlRange === "24h") cutoff.setHours(cutoff.getHours() - 24);
    else if (pnlRange === "7d") cutoff.setDate(cutoff.getDate() - 7);
    else cutoff.setDate(cutoff.getDate() - 30);
    const cutoffStr = cutoff.toISOString().slice(0, 16);
    return pnlData.filter((p) => p.time >= cutoffStr);
  })();

  // Render P&L snapshots chart
  useEffect(() => {
    if (!pnlChartContainerRef.current || filteredPnlData.length === 0) return;

    const isDark = document.documentElement.classList.contains("dark");
    const chart = createChart(pnlChartContainerRef.current, {
      width: pnlChartContainerRef.current.clientWidth,
      height: 300,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: isDark ? "#9ca3af" : "#6b7280",
      },
      grid: {
        vertLines: { color: isDark ? "#1f2937" : "#e5e7eb" },
        horzLines: { color: isDark ? "#1f2937" : "#e5e7eb" },
      },
      rightPriceScale: {
        borderColor: isDark ? "#374151" : "#d1d5db",
      },
      timeScale: {
        borderColor: isDark ? "#374151" : "#d1d5db",
        timeVisible: true,
      },
      crosshair: { mode: 0 },
    });

    const lastValue = filteredPnlData[filteredPnlData.length - 1]?.value ?? 0;
    const lineColor = lastValue >= 0 ? "#22c55e" : "#ef4444";

    const series = chart.addSeries(LineSeries, {
      color: lineColor,
      lineWidth: 2,
      priceFormat: { type: "price", precision: 2, minMove: 0.01 },
    });

    const data = filteredPnlData.map((p) => ({
      time: (new Date(p.time + ":00Z").getTime() / 1000) as unknown as UTCTimestamp,
      value: p.value,
    }));

    series.setData(data);
    chart.timeScale().fitContent();

    const resizeObserver = new ResizeObserver(() => {
      if (pnlChartContainerRef.current) {
        chart.applyOptions({ width: pnlChartContainerRef.current.clientWidth });
      }
    });
    resizeObserver.observe(pnlChartContainerRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
    };
  }, [filteredPnlData]);

  const handleConvert = async () => {
    const amount = parseFloat(convertAmount);
    if (!amount || amount <= 0) return;

    setConverting(true);
    setConvertResult(null);
    setConvertError(null);

    try {
      const result = await convertToBnb(amount);
      setConvertResult(
        `Achat de ${result.bnb_bought.toFixed(4)} BNB pour ${result.usdc_spent.toFixed(2)} USDC`
      );
      const balance = await fetchBnbBalance();
      setBnbFree(balance.free);
      setBnbLocked(balance.locked);
      setConvertAmount("");
    } catch (err) {
      setConvertError(err instanceof Error ? err.message : "Conversion failed");
    } finally {
      setConverting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-4rem)]">
        <p className="text-gray-500">Loading...</p>
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <h1 className="text-3xl font-bold mb-8">Dashboard</h1>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <div className="p-5 rounded-xl bg-gradient-to-br from-emerald-500/10 to-emerald-600/5 border border-emerald-500/20">
          <p className="text-xs font-medium text-emerald-600 dark:text-emerald-400 uppercase tracking-wide mb-1">
            Total P&L
          </p>
          <p
            className={`text-2xl font-bold ${
              totalPnl >= 0
                ? "text-emerald-600 dark:text-emerald-400"
                : "text-red-500"
            }`}
          >
            {totalPnl >= 0 ? "+" : ""}
            {totalPnl.toFixed(2)} $
          </p>
        </div>

        <div className="p-5 rounded-xl bg-gradient-to-br from-blue-500/10 to-blue-600/5 border border-blue-500/20">
          <p className="text-xs font-medium text-blue-600 dark:text-blue-400 uppercase tracking-wide mb-1">
            Realized
          </p>
          <p
            className={`text-2xl font-bold ${
              totalRealized >= 0
                ? "text-blue-600 dark:text-blue-400"
                : "text-red-500"
            }`}
          >
            {totalRealized >= 0 ? "+" : ""}
            {totalRealized.toFixed(2)} $
          </p>
        </div>

        <div className="p-5 rounded-xl bg-gradient-to-br from-violet-500/10 to-violet-600/5 border border-violet-500/20">
          <p className="text-xs font-medium text-violet-600 dark:text-violet-400 uppercase tracking-wide mb-1">
            Active Bots
          </p>
          <p className="text-2xl font-bold text-violet-600 dark:text-violet-400">
            {activeBots}
            <span className="text-sm font-normal text-gray-400 ml-1">
              / {bots.length}
            </span>
          </p>
        </div>

        <div className="p-5 rounded-xl bg-gradient-to-br from-amber-500/10 to-amber-600/5 border border-amber-500/20">
          <p className="text-xs font-medium text-amber-600 dark:text-amber-400 uppercase tracking-wide mb-1">
            Open Positions
          </p>
          <p className="text-2xl font-bold text-amber-600 dark:text-amber-400">
            {totalPositions}
          </p>
        </div>
      </div>

      {/* Daily Profit Chart */}
      <div className="mb-8 p-6 rounded-xl bg-gradient-to-br from-gray-50 to-gray-100/50 dark:from-gray-900/50 dark:to-gray-800/30 border border-gray-200 dark:border-gray-800">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold">Daily Profit</h2>
            <div className="flex rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden text-xs font-medium">
              {(["1m", "6m", "all"] as const).map((range) => (
                <button
                  key={range}
                  onClick={() => setProfitRange(range)}
                  className={`px-3 py-1.5 transition ${
                    profitRange === range
                      ? "bg-emerald-500 text-white"
                      : "text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
                  }`}
                >
                  {range === "1m" ? "1M" : range === "6m" ? "6M" : "All"}
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-4 text-sm">
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block" />
              <span className="text-gray-500 dark:text-gray-400">
                Today:{" "}
                <span
                  className={`font-medium ${
                    todayProfit >= 0
                      ? "text-emerald-600 dark:text-emerald-400"
                      : "text-red-500"
                  }`}
                >
                  {todayProfit >= 0 ? "+" : ""}
                  {todayProfit.toFixed(2)} $
                </span>
              </span>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-blue-500 inline-block" />
              <span className="text-gray-500 dark:text-gray-400">
                Best day:{" "}
                <span className="font-medium text-blue-600 dark:text-blue-400">
                  +{bestDay.toFixed(2)} $
                </span>
              </span>
            </span>
          </div>
        </div>
        {filteredProfitData.length > 0 ? (
          <div ref={chartContainerRef} />
        ) : (
          <p className="text-gray-400 text-sm py-10 text-center">
            No trade data yet.
          </p>
        )}
      </div>

      {/* Cumulative P&L Chart */}
      <div className="mb-8 p-6 rounded-xl bg-gradient-to-br from-gray-50 to-gray-100/50 dark:from-gray-900/50 dark:to-gray-800/30 border border-gray-200 dark:border-gray-800">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold">Cumulative P&L</h2>
            <div className="flex rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden text-xs font-medium">
              {(["24h", "7d", "30d"] as const).map((range) => (
                <button
                  key={range}
                  onClick={() => setPnlRange(range)}
                  className={`px-3 py-1.5 transition ${
                    pnlRange === range
                      ? "bg-emerald-500 text-white"
                      : "text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
                  }`}
                >
                  {range}
                </button>
              ))}
            </div>
          </div>
          {filteredPnlData.length > 0 && (
            <span className="text-sm text-gray-500 dark:text-gray-400">
              Latest:{" "}
              <span
                className={`font-medium ${
                  filteredPnlData[filteredPnlData.length - 1].value >= 0
                    ? "text-emerald-600 dark:text-emerald-400"
                    : "text-red-500"
                }`}
              >
                {filteredPnlData[filteredPnlData.length - 1].value >= 0 ? "+" : ""}
                {filteredPnlData[filteredPnlData.length - 1].value.toFixed(2)} $
              </span>
            </span>
          )}
        </div>
        {filteredPnlData.length > 0 ? (
          <div ref={pnlChartContainerRef} />
        ) : (
          <p className="text-gray-400 text-sm py-10 text-center">
            No snapshot data yet. Data will appear after the first hourly snapshot.
          </p>
        )}
      </div>

      {/* Info Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div className="p-5 rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900/30">
          <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-1">
            Email
          </p>
          <p className="text-lg font-semibold truncate">{user.email}</p>
        </div>

        <div className="p-5 rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900/30">
          <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-1">
            Role
          </p>
          <p className="text-lg font-semibold capitalize">{user.role}</p>
        </div>

        <div className="p-5 rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900/30">
          <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-1">
            Binance API
          </p>
          <p className="text-lg font-semibold">
            {user.binance_api_key ? (
              <span className="text-emerald-600 dark:text-emerald-400">
                Connected
              </span>
            ) : (
              <span className="text-gray-400">Not configured</span>
            )}
          </p>
        </div>
      </div>

      {/* Services Monitoring */}
      {health && (
        <div className="mb-8 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Redis */}
          <div className={`p-4 rounded-xl border ${
            health.redis.connected
              ? "border-emerald-500/20 bg-gradient-to-br from-emerald-500/10 to-teal-500/5"
              : "border-red-500/20 bg-gradient-to-br from-red-500/10 to-red-500/5"
          }`}>
            <div className="flex items-center gap-2 mb-2">
              <span className={`w-2 h-2 rounded-full ${health.redis.connected ? "bg-emerald-500" : "bg-red-500"}`} />
              <p className="text-sm font-semibold">Redis</p>
            </div>
            {health.redis.connected ? (
              <div className="space-y-1 text-xs text-gray-500 dark:text-gray-400">
                <p>Memory: <span className="font-medium text-gray-700 dark:text-gray-300">{health.redis.used_memory_human}</span></p>
                <p>Clients: <span className="font-medium text-gray-700 dark:text-gray-300">{health.redis.connected_clients}</span></p>
                <p>Prices cached: <span className="font-medium text-gray-700 dark:text-gray-300">{health.redis.cached_prices}</span></p>
                <p>Bot locks: <span className="font-medium text-gray-700 dark:text-gray-300">{health.redis.active_bot_locks}</span></p>
              </div>
            ) : (
              <p className="text-xs text-red-500">Disconnected</p>
            )}
          </div>

          {/* Database */}
          <div className={`p-4 rounded-xl border ${
            health.database.connected
              ? "border-emerald-500/20 bg-gradient-to-br from-emerald-500/10 to-teal-500/5"
              : "border-red-500/20 bg-gradient-to-br from-red-500/10 to-red-500/5"
          }`}>
            <div className="flex items-center gap-2 mb-2">
              <span className={`w-2 h-2 rounded-full ${health.database.connected ? "bg-emerald-500" : "bg-red-500"}`} />
              <p className="text-sm font-semibold">MariaDB</p>
            </div>
            {health.database.connected ? (
              <p className="text-xs text-gray-500 dark:text-gray-400">Connected</p>
            ) : (
              <p className="text-xs text-red-500">{health.database.error || "Disconnected"}</p>
            )}
          </div>

          {/* Celery Workers */}
          <div className={`p-4 rounded-xl border ${
            health.celery.online > 0
              ? "border-emerald-500/20 bg-gradient-to-br from-emerald-500/10 to-teal-500/5"
              : "border-red-500/20 bg-gradient-to-br from-red-500/10 to-red-500/5"
          }`}>
            <div className="flex items-center gap-2 mb-2">
              <span className={`w-2 h-2 rounded-full ${health.celery.online > 0 ? "bg-emerald-500" : "bg-red-500"}`} />
              <p className="text-sm font-semibold">Celery</p>
              <span className="text-xs text-gray-400">{health.celery.online} worker{health.celery.online !== 1 ? "s" : ""}</span>
            </div>
            {health.celery.workers.length > 0 ? (
              <div className="space-y-1.5 text-xs">
                {health.celery.workers.map((w) => (
                  <div key={w.name} className="flex items-center justify-between text-gray-500 dark:text-gray-400">
                    <span className="truncate max-w-[120px]" title={w.name}>
                      {w.name.split("@")[0]}
                    </span>
                    <span className="font-medium text-gray-700 dark:text-gray-300">
                      {w.active_tasks} / {w.concurrency}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-red-500">No workers online</p>
            )}
          </div>

          {/* Price Feed */}
          <div className={`p-4 rounded-xl border ${
            health.price_feed.status === "ok"
              ? "border-emerald-500/20 bg-gradient-to-br from-emerald-500/10 to-teal-500/5"
              : health.price_feed.status === "degraded"
              ? "border-amber-500/20 bg-gradient-to-br from-amber-500/10 to-yellow-500/5"
              : "border-red-500/20 bg-gradient-to-br from-red-500/10 to-red-500/5"
          }`}>
            <div className="flex items-center gap-2 mb-2">
              <span className={`w-2 h-2 rounded-full ${
                health.price_feed.status === "ok" ? "bg-emerald-500"
                : health.price_feed.status === "degraded" ? "bg-amber-500"
                : "bg-red-500"
              }`} />
              <p className="text-sm font-semibold">Price Feed</p>
            </div>
            <div className="space-y-1 text-xs text-gray-500 dark:text-gray-400">
              <p>Fresh: <span className="font-medium text-gray-700 dark:text-gray-300">{health.price_feed.fresh_prices}</span></p>
              {health.price_feed.stale_prices > 0 && (
                <p>Stale: <span className="font-medium text-amber-600 dark:text-amber-400">{health.price_feed.stale_prices}</span></p>
              )}
              {health.price_feed.stale_symbols && health.price_feed.stale_symbols.length > 0 && (
                <p className="text-amber-500 truncate" title={health.price_feed.stale_symbols.join(", ")}>
                  {health.price_feed.stale_symbols.join(", ")}
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* BNB Section */}
      {user.binance_api_key && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* USDC Balance */}
          <div className="p-5 rounded-xl bg-gradient-to-br from-emerald-500/10 to-teal-500/5 border border-emerald-500/20">
            <p className="text-xs font-medium text-emerald-600 dark:text-emerald-400 uppercase tracking-wide mb-2">
              USDC disponible
            </p>
            {bnbLoading ? (
              <p className="text-gray-400">Chargement...</p>
            ) : usdcFree !== null ? (
              <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">
                {usdcFree.toFixed(2)} $
              </p>
            ) : (
              <p className="text-gray-400">Indisponible</p>
            )}
          </div>

          {/* BNB Balance */}
          <div className="p-5 rounded-xl bg-gradient-to-br from-yellow-500/10 to-orange-500/5 border border-yellow-500/20">
            <p className="text-xs font-medium text-yellow-600 dark:text-yellow-400 uppercase tracking-wide mb-2">
              BNB disponible
            </p>
            {bnbLoading ? (
              <p className="text-gray-400">Chargement...</p>
            ) : bnbFree !== null ? (
              <div>
                <p className="text-2xl font-bold text-yellow-600 dark:text-yellow-400">
                  {bnbFree.toFixed(6)} BNB
                </p>
                {bnbPrice !== null && (
                  <p className="text-sm text-gray-500 mt-1">
                    ~ {(bnbFree * bnbPrice).toFixed(2)} $
                  </p>
                )}
                {(bnbLocked ?? 0) > 0 && (
                  <p className="text-sm text-gray-500 mt-1">
                    + {bnbLocked?.toFixed(6)} locked
                  </p>
                )}
              </div>
            ) : (
              <p className="text-gray-400">Indisponible</p>
            )}
          </div>

          {/* Convert USDC to BNB */}
          <div className="p-5 rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900/30">
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-3">
              Convertir USDC en BNB
            </p>
            <div className="flex gap-3">
              <input
                type="number"
                min="0"
                step="0.01"
                placeholder="Montant USDC"
                value={convertAmount}
                onChange={(e) => setConvertAmount(e.target.value)}
                className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-transparent focus:outline-none focus:ring-2 focus:ring-yellow-500"
              />
              <button
                onClick={handleConvert}
                disabled={converting || !convertAmount}
                className="px-4 py-2 bg-gradient-to-r from-yellow-500 to-orange-500 text-white rounded-lg hover:from-yellow-600 hover:to-orange-600 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap font-medium"
              >
                {converting ? "..." : "Acheter BNB"}
              </button>
            </div>
            {convertResult && (
              <p className="mt-2 text-sm text-emerald-600 dark:text-emerald-400">
                {convertResult}
              </p>
            )}
            {convertError && (
              <p className="mt-2 text-sm text-red-500">{convertError}</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
