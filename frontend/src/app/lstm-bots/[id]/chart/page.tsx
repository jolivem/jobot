"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import {
  createChart,
  CandlestickSeries,
  LineSeries,
  ColorType,
  CrosshairMode,
  type IChartApi,
  type UTCTimestamp,
} from "lightweight-charts";
import {
  fetchLstmBotKlines,
  fetchLstmSlopeHistory,
  fetchLstmSlopes,
  listLstmBots,
  type Kline,
  type LstmBot,
  type SlopeInfo,
  type SlopePoint,
} from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

const TIMEFRAMES = [
  { label: "24h", interval: "5m", limit: 288 },
  { label: "7d", interval: "1h", limit: 168 },
  { label: "60d", interval: "4h", limit: 360 },
] as const;

type TimeframeKey = (typeof TIMEFRAMES)[number]["label"];

const SLOPE_COLORS: Record<string, string> = {
  "15m": "#a78bfa",
  "1d": "#38bdf8",
  "1w": "#fb923c",
  "1h": "#a78bfa",
  "4h": "#38bdf8",
  "30m": "#a78bfa",
};

export default function LstmChartPage() {
  const router = useRouter();
  const params = useParams();
  const botId = Number(params.id);
  const { isAuthenticated, loading: authLoading } = useAuth();

  const priceContainerRef = useRef<HTMLDivElement>(null);
  const priceChartRef = useRef<IChartApi | null>(null);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);

  const [bot, setBot] = useState<LstmBot | null>(null);
  const [slopes, setSlopes] = useState<SlopeInfo[]>([]);
  const [slopeHistory, setSlopeHistory] = useState<Record<string, SlopePoint[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeTimeframe, setActiveTimeframe] = useState<TimeframeKey>("7d");

  useEffect(() => {
    if (!authLoading && !isAuthenticated) router.push("/login");
  }, [authLoading, isAuthenticated, router]);

  // Load bot + slope history (once)
  useEffect(() => {
    if (authLoading || !isAuthenticated || !botId) return;

    listLstmBots()
      .then((bots) => {
        const found = bots.find((b) => b.id === botId);
        if (!found) {
          setError("Bot not found");
          return;
        }
        setBot(found);
        if (found.model_status === "ready") {
          fetchLstmSlopes(found.id).then(setSlopes).catch(() => {});
          fetchLstmSlopeHistory(found.id, 300).then(setSlopeHistory).catch(() => {});
        }
      })
      .catch((err) => setError(err.message || "Failed to load bot"))
      .finally(() => setLoading(false));
  }, [authLoading, isAuthenticated, router, botId]);

  // Render both charts
  const renderCharts = useCallback(
    (klines: Kline[], slopeData: Record<string, SlopePoint[]>, botInfo: LstmBot) => {
      if (!priceContainerRef.current || klines.length === 0) return;

      // Cleanup
      resizeObserverRef.current?.disconnect();
      resizeObserverRef.current = null;
      if (priceChartRef.current) { priceChartRef.current.remove(); priceChartRef.current = null; }

      const chartOpts = {
        layout: {
          background: { type: ColorType.Solid as const, color: "#1a1a2e" },
          textColor: "#d1d5db",
        },
        grid: { vertLines: { color: "#2a2a4a" }, horzLines: { color: "#2a2a4a" } },
        crosshair: { mode: CrosshairMode.Normal },
        timeScale: { timeVisible: true, secondsVisible: false },
      };

      // === Single chart with price + slopes ===
      const chart = createChart(priceContainerRef.current!, {
        ...chartOpts,
        width: priceContainerRef.current!.clientWidth,
        height: 500,
        rightPriceScale: { visible: true },
        leftPriceScale: { visible: true },
      });
      priceChartRef.current = chart;

      // Candlesticks on right axis
      chart.addSeries(CandlestickSeries, {
        upColor: "#22c55e", downColor: "#ef4444",
        borderDownColor: "#ef4444", borderUpColor: "#22c55e",
        wickDownColor: "#ef4444", wickUpColor: "#22c55e",
        priceScaleId: "right",
      }).setData(klines.map((k) => ({ ...k, time: k.time as UTCTimestamp })));

      // Slope lines on left axis
      const hasSlopeData = Object.values(slopeData).some((h) => h.length > 0);
      if (hasSlopeData) {
        const priceTimeMin = klines[0].time;
        const priceTimeMax = klines[klines.length - 1].time;

        // Resample slope data to candle timestamps to avoid stretching the time axis
        const candleTimes = new Set(klines.map((k) => k.time));

        const timeframes = botInfo.timeframes.split(",");
        for (const tf of timeframes) {
          const history = slopeData[tf];
          if (!history || history.length === 0) continue;

          const filtered = history.filter((p) => p.time >= priceTimeMin && p.time <= priceTimeMax);
          if (filtered.length === 0) continue;

          // Snap each slope point to the nearest candle time
          const resampled: { time: number; value: number }[] = [];
          const usedTimes = new Set<number>();

          for (const candle of klines) {
            // Find the latest slope point at or before this candle time
            let best: SlopePoint | null = null;
            for (const p of filtered) {
              if (p.time <= candle.time) {
                if (!best || p.time > best.time) best = p;
              }
            }
            if (best && !usedTimes.has(candle.time)) {
              resampled.push({ time: candle.time, value: best.slope });
              usedTimes.add(candle.time);
            }
          }

          if (resampled.length === 0) continue;

          chart.addSeries(LineSeries, {
            color: SLOPE_COLORS[tf] || "#94a3b8",
            lineWidth: 2,
            crosshairMarkerVisible: false,
            lastValueVisible: true,
            priceLineVisible: false,
            title: `slope ${tf}`,
            priceScaleId: "left",
          }).setData(resampled.map((p) => ({ time: p.time as UTCTimestamp, value: p.value })));
        }

        // Zero line on left axis (using a dedicated series with price line)
        const zeroSeries = chart.addSeries(LineSeries, {
          color: "transparent", lineWidth: 0,
          crosshairMarkerVisible: false, lastValueVisible: false, priceLineVisible: false,
          priceScaleId: "left",
        });
        zeroSeries.setData([
          { time: priceTimeMin as UTCTimestamp, value: 0 },
          { time: priceTimeMax as UTCTimestamp, value: 0 },
        ]);
        zeroSeries.createPriceLine({
          price: 0,
          color: "#6b7280",
          lineWidth: 1,
          lineStyle: 2,
          axisLabelVisible: true,
          title: "",
        });
      }

      chart.timeScale().fitContent();

      // Responsive resize
      const ro = new ResizeObserver((entries) => {
        for (const entry of entries) {
          priceChartRef.current?.applyOptions({ width: entry.contentRect.width });
        }
      });
      ro.observe(priceContainerRef.current!);
      resizeObserverRef.current = ro;
    },
    []
  );

  // Fetch klines + render when timeframe or bot changes
  useEffect(() => {
    if (!bot) return;
    const tf = TIMEFRAMES.find((t) => t.label === activeTimeframe)!;
    let cancelled = false;

    fetchLstmBotKlines(botId, tf.interval, tf.limit)
      .then((klines) => {
        if (!cancelled) renderCharts(klines, slopeHistory, bot);
      })
      .catch((e) => console.error("klines fetch error:", e));

    return () => { cancelled = true; };
  }, [bot, activeTimeframe, botId, slopeHistory, renderCharts]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      resizeObserverRef.current?.disconnect();
      priceChartRef.current?.remove();
    };
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-4rem)]">
        <p className="text-gray-500">Loading chart...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        <p className="text-red-500">{error}</p>
        <Link href={`/lstm-bots/${botId}`} className="text-blue-600 hover:underline mt-4 inline-block">Back to bot</Link>
      </div>
    );
  }

  const tf = TIMEFRAMES.find((t) => t.label === activeTimeframe)!;
  const intervalLabel = tf.interval === "5m" ? "5min" : tf.interval === "1h" ? "1h" : "4h";
  const timeframes = bot?.timeframes.split(",") || [];

  const slopeColors: Record<string, string> = { up: "text-green-400", down: "text-red-400", neutral: "text-gray-400" };
  const slopeArrows: Record<string, string> = { up: "\u2191", down: "\u2193", neutral: "\u2192" };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold">
            {bot?.symbol}
            <span className="ml-2 text-sm font-normal text-purple-400">LSTM</span>
            <span className="ml-2 text-sm font-normal text-gray-400">— {activeTimeframe}</span>
          </h1>
          <p className="text-gray-500 text-sm mt-1">
            {intervalLabel} candles &middot; Models: {bot?.timeframes} &middot;
            TP: {bot?.take_profit_pct}% / SL: {bot?.stop_loss_pct}%
          </p>
        </div>
        <Link href={`/lstm-bots/${botId}`}
          className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition">
          Back
        </Link>
      </div>

      {/* Current slopes */}
      {slopes.length > 0 && (
        <div className="flex gap-6 mb-4 p-3 rounded-lg bg-gray-900/50 border border-gray-800">
          {slopes.map((s) => (
            <div key={s.timeframe} className="flex items-center gap-2">
              <span className="text-xs text-gray-400">{s.timeframe}</span>
              <span className={`text-lg font-bold ${slopeColors[s.direction]}`}>{slopeArrows[s.direction]}</span>
              <span className={`text-sm font-medium ${slopeColors[s.direction]}`}>
                {s.slope >= 0 ? "+" : ""}{s.slope.toFixed(4)}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Timeframe selector */}
      <div className="flex gap-2 mb-4">
        {TIMEFRAMES.map((t) => (
          <button key={t.label} onClick={() => setActiveTimeframe(t.label)}
            className={`px-4 py-2 text-sm font-medium rounded-lg transition ${
              activeTimeframe === t.label
                ? "bg-purple-600 text-white"
                : "bg-gray-200 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-700"
            }`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Chart */}
      <div className="rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden">
        <div ref={priceContainerRef} />
      </div>

      {/* Legend */}
      <div className="mt-4 flex gap-4 text-xs text-gray-500 flex-wrap">
        <span className="flex items-center gap-1">
          <span className="inline-block w-4 h-0.5 bg-green-500" /> Bullish
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-4 h-0.5 bg-red-500" /> Bearish
        </span>
        <span className="inline-block mx-1 text-gray-700">|</span>
        {timeframes.map((tf) => (
          <span key={tf} className="flex items-center gap-1">
            <span className="inline-block w-4 h-0.5" style={{ backgroundColor: SLOPE_COLORS[tf] || "#94a3b8" }} />
            Slope {tf}
          </span>
        ))}
      </div>
    </div>
  );
}
