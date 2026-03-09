"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import {
  createChart,
  createSeriesMarkers,
  CandlestickSeries,
  LineSeries,
  ColorType,
  CrosshairMode,
  type IChartApi,
  type UTCTimestamp,
} from "lightweight-charts";
import {
  fetchBotKlines,
  fetchBotTrades,
  listBots,
  type Kline,
  type Trade,
  type TradingBot,
} from "@/lib/api";
import { computeTradePositionNumbers } from "@/lib/tradePositions";
import { useAuth } from "@/contexts/AuthContext";

const TIMEFRAMES = [
  { label: "24h", interval: "5m", limit: 288, snapSeconds: 300 },
  { label: "7d", interval: "1h", limit: 168, snapSeconds: 3600 },
  { label: "60d", interval: "4h", limit: 360, snapSeconds: 14400 },
] as const;

type TimeframeKey = (typeof TIMEFRAMES)[number]["label"];

function computeGrid(maxPrice: number, minPrice: number, gridLevels: number): number[] {
  if (gridLevels <= 1 || maxPrice <= minPrice) return [];
  const step = (maxPrice - minPrice) / gridLevels;
  return Array.from({ length: gridLevels - 1 }, (_, i) => maxPrice - (i + 1) * step);
}

export default function ChartPage() {
  const router = useRouter();
  const params = useParams();
  const botId = Number(params.id);
  const { isAuthenticated, loading: authLoading } = useAuth();

  const chartContainerRef = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);
  const disposedRef = useRef(false);

  const [bot, setBot] = useState<TradingBot | null>(null);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeTimeframe, setActiveTimeframe] = useState<TimeframeKey>("7d");

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [authLoading, isAuthenticated, router]);

  // Initial load: bot info + trades (fetched once)
  useEffect(() => {
    if (authLoading || !isAuthenticated || !botId) return;

    const load = async () => {
      try {
        const [bots, botTrades] = await Promise.all([
          listBots(),
          fetchBotTrades(botId),
        ]);
        const currentBot = bots.find((b) => b.id === botId);
        if (!currentBot) {
          setError("Bot not found");
          setLoading(false);
          return;
        }
        setBot(currentBot);
        setTrades(botTrades);
      } catch {
        setError("Failed to load chart data");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [authLoading, isAuthenticated, router, botId]);

  const renderChart = useCallback(
    (bot: TradingBot, klines: Kline[], trades: Trade[], snapSeconds: number) => {
      if (!chartContainerRef.current || klines.length === 0) return;

      // Clean up previous chart
      resizeObserverRef.current?.disconnect();
      resizeObserverRef.current = null;
      if (chartRef.current) {
        disposedRef.current = true;
        chartRef.current.remove();
        chartRef.current = null;
      }

      // Allow pending RAFs from old chart to fire harmlessly
      requestAnimationFrame(() => {
        disposedRef.current = false;
      });

      const chart = createChart(chartContainerRef.current!, {
        layout: {
          background: { type: ColorType.Solid, color: "#1a1a2e" },
          textColor: "#d1d5db",
        },
        grid: {
          vertLines: { color: "#2a2a4a" },
          horzLines: { color: "#2a2a4a" },
        },
        crosshair: { mode: CrosshairMode.Normal },
        width: chartContainerRef.current!.clientWidth,
        height: 500,
        timeScale: {
          timeVisible: true,
          secondsVisible: false,
        },
      });
      chartRef.current = chart;

      const candleSeries = chart.addSeries(CandlestickSeries, {
        upColor: "#22c55e",
        downColor: "#ef4444",
        borderDownColor: "#ef4444",
        borderUpColor: "#22c55e",
        wickDownColor: "#ef4444",
        wickUpColor: "#22c55e",
      });

      candleSeries.setData(
        klines.map((k) => ({ ...k, time: k.time as UTCTimestamp }))
      );

      // Min/Max price lines
      candleSeries.createPriceLine({
        price: bot.max_price,
        color: "#f59e0b",
        lineWidth: 2,
        lineStyle: 0,
        axisLabelVisible: true,
        title: "Max",
      });
      candleSeries.createPriceLine({
        price: bot.min_price,
        color: "#f59e0b",
        lineWidth: 2,
        lineStyle: 0,
        axisLabelVisible: true,
        title: "Min",
      });

      // Grid levels
      const gridLevels = computeGrid(bot.max_price, bot.min_price, bot.grid_levels);
      for (const level of gridLevels) {
        candleSeries.createPriceLine({
          price: level,
          color: "#6366f1",
          lineWidth: 1,
          lineStyle: 2,
          axisLabelVisible: false,
          title: "",
        });
      }

      // Trade markers
      const klineStartTime = klines[0]?.time ?? 0;
      const recentTrades = trades.filter((t) => {
        const utcStr = t.created_at.endsWith("Z") || t.created_at.includes("+") ? t.created_at : t.created_at + "Z";
        return new Date(utcStr).getTime() / 1000 >= klineStartTime;
      });

      const toUtc = (s: string) =>
        s.endsWith("Z") || s.includes("+") ? s : s + "Z";
      const snapTime = (s: string) => {
        const sec = Math.floor(new Date(toUtc(s)).getTime() / 1000);
        return sec - (sec % snapSeconds);
      };

      if (recentTrades.length > 0) {
        const sorted = [...recentTrades].sort(
          (a, b) => new Date(toUtc(a.created_at)).getTime() - new Date(toUtc(b.created_at)).getTime()
        );

        const positionNumbers = computeTradePositionNumbers(trades);
        const MARKER_COLOR = "#fef9c3"; // very light yellow

        // Map snapped time → trades for tooltip lookup
        const markersByTime = new Map<number, Array<{ trade: Trade; pos: number | undefined }>>();
        for (const t of sorted) {
          const snapped = snapTime(t.created_at);
          if (!markersByTime.has(snapped)) markersByTime.set(snapped, []);
          markersByTime.get(snapped)!.push({ trade: t, pos: positionNumbers.get(t.id) });
        }

        // Use invisible LineSeries anchored at trade.price so markers appear at exact price level.
        // Deduplicate by snapped time (last trade wins per candle per side).
        const buyByTime = new Map<number, { trade: Trade; pos: number | undefined }>();
        const sellByTime = new Map<number, { trade: Trade; pos: number | undefined }>();
        for (const t of sorted) {
          const snapped = snapTime(t.created_at);
          const entry = { trade: t, pos: positionNumbers.get(t.id) };
          if (t.trade_type === "buy") buyByTime.set(snapped, entry);
          else sellByTime.set(snapped, entry);
        }

        const makeGhostSeries = (
          entries: Map<number, { trade: Trade; pos: number | undefined }>,
          shape: "arrowUp" | "arrowDown"
        ) => {
          if (entries.size === 0) return;
          const series = chart.addSeries(LineSeries, {
            color: "transparent",
            lineWidth: 1,
            crosshairMarkerVisible: false,
            lastValueVisible: false,
            priceLineVisible: false,
          });
          const sorted = [...entries.entries()].sort(([a], [b]) => a - b);
          series.setData(sorted.map(([time, { trade }]) => ({ time: time as UTCTimestamp, value: trade.price })));
          createSeriesMarkers(series, sorted.map(([time, { pos }]) => ({
            time: time as UTCTimestamp,
            position: "inBar" as const,
            color: MARKER_COLOR,
            shape,
            text: pos !== undefined ? `#${pos}` : "",
          })));
        };

        makeGhostSeries(buyByTime, "arrowUp");
        makeGhostSeries(sellByTime, "arrowDown");

        // Crosshair tooltip
        chart.subscribeCrosshairMove((param) => {
          const tooltip = tooltipRef.current;
          if (!tooltip) return;

          if (!param.time || !param.point) {
            tooltip.style.display = "none";
            return;
          }

          const tradesAtTime = markersByTime.get(param.time as number);
          if (!tradesAtTime || tradesAtTime.length === 0) {
            tooltip.style.display = "none";
            return;
          }

          const parts = tradesAtTime.map(({ trade, pos }) => {
            const date = new Date(toUtc(trade.created_at)).toLocaleString();
            const color = trade.trade_type === "buy" ? "#22c55e" : "#ef4444";
            return `<div style="color:${color};font-weight:600;margin-bottom:2px">${trade.trade_type.toUpperCase()}${pos !== undefined ? ` #${pos}` : ""}</div>`
              + `<div style="color:#9ca3af">${date}</div>`
              + `<div>Prix : <span style="font-family:monospace">${trade.price.toFixed(8)}</span></div>`
              + `<div>Qté : <span style="font-family:monospace">${trade.quantity.toFixed(6)}</span></div>`;
          });

          tooltip.innerHTML = parts.join('<hr style="border-color:#374151;margin:6px 0">');

          const containerWidth = chartContainerRef.current?.clientWidth ?? 0;
          const tooltipWidth = 210;
          const left = param.point.x + 14 + tooltipWidth > containerWidth
            ? param.point.x - tooltipWidth - 14
            : param.point.x + 14;

          tooltip.style.display = "block";
          tooltip.style.left = `${left}px`;
          tooltip.style.top = `${Math.max(0, param.point.y - 20)}px`;
        });
      }

      // Responsive resize
      const resizeObserver = new ResizeObserver((entries) => {
        if (disposedRef.current || !chartRef.current) return;
        for (const entry of entries) {
          chart.applyOptions({ width: entry.contentRect.width });
        }
      });
      resizeObserver.observe(chartContainerRef.current!);
      resizeObserverRef.current = resizeObserver;

      chart.timeScale().fitContent();
    },
    []
  );

  // Fetch klines and render chart when timeframe or bot changes
  useEffect(() => {
    if (!bot) return;

    const tf = TIMEFRAMES.find((t) => t.label === activeTimeframe)!;

    let cancelled = false;
    fetchBotKlines(botId, tf.interval, tf.limit).then((klines) => {
      if (!cancelled) {
        renderChart(bot, klines, trades, tf.snapSeconds);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [bot, trades, activeTimeframe, botId, renderChart]);

  // Cleanup on unmount only
  useEffect(() => {
    return () => {
      resizeObserverRef.current?.disconnect();
      resizeObserverRef.current = null;
      if (chartRef.current) {
        disposedRef.current = true;
        chartRef.current.remove();
        chartRef.current = null;
      }
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
        <Link href={`/bots/${botId}`} className="text-blue-600 hover:underline mt-4 inline-block">
          Back to bots
        </Link>
      </div>
    );
  }

  const tf = TIMEFRAMES.find((t) => t.label === activeTimeframe)!;
  const intervalLabel = tf.interval === "5m" ? "5min" : tf.interval === "1h" ? "1h" : "4h";

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold">{bot?.symbol} — {activeTimeframe} Chart</h1>
          <p className="text-gray-500 text-sm mt-1">
            {intervalLabel} candles &middot; Grid: {bot?.grid_levels} levels &middot;
            Range: {bot?.min_price} – {bot?.max_price}
          </p>
        </div>
        <Link
          href={`/bots/${botId}`}
          className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition"
        >
          Back
        </Link>
      </div>

      {/* Timeframe selector */}
      <div className="flex gap-2 mb-4">
        {TIMEFRAMES.map((tf) => (
          <button
            key={tf.label}
            onClick={() => setActiveTimeframe(tf.label)}
            className={`px-4 py-2 text-sm font-medium rounded-lg transition ${
              activeTimeframe === tf.label
                ? "bg-indigo-600 text-white"
                : "bg-gray-200 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-700"
            }`}
          >
            {tf.label}
          </button>
        ))}
      </div>

      <div className="rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden relative">
        <div ref={chartContainerRef} />
        <div
          ref={tooltipRef}
          className="absolute z-10 pointer-events-none bg-gray-900 border border-gray-700 rounded-lg p-3 text-xs text-gray-200 shadow-xl"
          style={{ minWidth: "180px", maxWidth: "210px", display: "none" }}
        />
      </div>

      <div className="mt-4 flex gap-4 text-xs text-gray-500">
        <span className="flex items-center gap-1">
          <span className="inline-block w-4 h-0.5 bg-amber-500" /> Min / Max
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-4 h-0.5 bg-indigo-500 border-dashed" style={{ borderTop: "2px dashed #6366f1", height: 0 }} /> Grid levels
        </span>
        <span className="flex items-center gap-1">
          <span style={{ color: "#fef9c3" }}>▲</span> Buy
        </span>
        <span className="flex items-center gap-1">
          <span style={{ color: "#fef9c3" }}>▼</span> Sell
        </span>
      </div>
    </div>
  );
}
