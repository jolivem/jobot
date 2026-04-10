"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
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

interface BotChartProps {
  bot: TradingBot;
  trades: Trade[];
  activeTimeframe: TimeframeKey;
}

function BotChart({ bot, trades, activeTimeframe }: BotChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);
  const disposedRef = useRef(false);

  const renderChart = useCallback(
    (bot: TradingBot, klines: Kline[], trades: Trade[], snapSeconds: number) => {
      if (!chartContainerRef.current || klines.length === 0) return;

      resizeObserverRef.current?.disconnect();
      resizeObserverRef.current = null;
      if (chartRef.current) {
        disposedRef.current = true;
        chartRef.current.remove();
        chartRef.current = null;
      }

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
        height: 400,
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
        const MARKER_COLOR = "#fef9c3";

        const markersByTime = new Map<number, Array<{ trade: Trade; pos: number | undefined }>>();
        for (const t of sorted) {
          const snapped = snapTime(t.created_at);
          if (!markersByTime.has(snapped)) markersByTime.set(snapped, []);
          markersByTime.get(snapped)!.push({ trade: t, pos: positionNumbers.get(t.id) });
        }

        const buys = sorted.filter((t) => t.trade_type === "buy");
        const sells = sorted.filter((t) => t.trade_type === "sell");

        const makeGhostSeries = (
          tradesToMark: Trade[],
          shape: "arrowUp" | "arrowDown"
        ) => {
          if (tradesToMark.length === 0) return;

          const lanes: Array<Array<{ time: number; trade: Trade; pos: number | undefined }>> = [];
          const timeSlotCount = new Map<number, number>();

          for (const t of tradesToMark) {
            const snapped = snapTime(t.created_at);
            const slot = timeSlotCount.get(snapped) ?? 0;
            timeSlotCount.set(snapped, slot + 1);
            if (!lanes[slot]) lanes[slot] = [];
            lanes[slot].push({ time: snapped, trade: t, pos: positionNumbers.get(t.id) });
          }

          for (const lane of lanes) {
            const series = chart.addSeries(LineSeries, {
              color: "transparent",
              lineWidth: 1,
              crosshairMarkerVisible: false,
              lastValueVisible: false,
              priceLineVisible: false,
            });
            const sortedLane = lane.sort((a, b) => a.time - b.time);
            series.setData(sortedLane.map((e) => ({ time: e.time as UTCTimestamp, value: e.trade.price })));
            createSeriesMarkers(series, sortedLane.map((e) => ({
              time: e.time as UTCTimestamp,
              position: "inBar" as const,
              color: MARKER_COLOR,
              shape,
              text: e.pos !== undefined ? `#${e.pos}` : "",
            })));
          }
        };

        makeGhostSeries(buys, "arrowUp");
        makeGhostSeries(sells, "arrowDown");

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

  useEffect(() => {
    const tf = TIMEFRAMES.find((t) => t.label === activeTimeframe)!;

    let cancelled = false;
    fetchBotKlines(bot.id, tf.interval, tf.limit).then((klines) => {
      if (!cancelled) {
        renderChart(bot, klines, trades, tf.snapSeconds);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [bot, trades, activeTimeframe, renderChart]);

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

  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden relative">
      <div ref={chartContainerRef} />
      <div
        ref={tooltipRef}
        className="absolute z-10 pointer-events-none bg-gray-900 border border-gray-700 rounded-lg p-3 text-xs text-gray-200 shadow-xl"
        style={{ minWidth: "180px", maxWidth: "210px", display: "none" }}
      />
    </div>
  );
}

export default function ChartsPage() {
  const router = useRouter();
  const { isAuthenticated, loading: authLoading } = useAuth();

  const [bots, setBots] = useState<TradingBot[]>([]);
  const [tradesMap, setTradesMap] = useState<Record<number, Trade[]>>({});
  const [loading, setLoading] = useState(true);
  const [activeTimeframe, setActiveTimeframe] = useState<TimeframeKey>("7d");

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [authLoading, isAuthenticated, router]);

  useEffect(() => {
    if (authLoading || !isAuthenticated) return;

    const load = async () => {
      try {
        const allBots = await listBots();
        const activeBots = allBots.filter((b) => b.is_active);
        setBots(activeBots);

        const tradesEntries = await Promise.all(
          activeBots.map(async (bot) => {
            const trades = await fetchBotTrades(bot.id);
            return [bot.id, trades] as [number, Trade[]];
          })
        );
        setTradesMap(Object.fromEntries(tradesEntries));
      } catch {
        // silently fail
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [authLoading, isAuthenticated, router]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-4rem)]">
        <p className="text-gray-500">Loading charts...</p>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Charts</h1>
        <div className="flex gap-2">
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
      </div>

      {bots.length === 0 ? (
        <p className="text-gray-400 text-center py-20">No active bots.</p>
      ) : (
        <div className="space-y-8">
          {bots.map((bot) => (
            <div key={bot.id}>
              <div className="flex items-center gap-3 mb-3">
                <Link
                  href={`/bots/${bot.id}`}
                  className="text-lg font-semibold text-blue-600 dark:text-blue-400 hover:underline"
                >
                  {bot.symbol}
                </Link>
                <span className="text-sm text-gray-500">
                  Range: {bot.min_price} – {bot.max_price} &middot; Grid: {bot.grid_levels} levels
                </span>
              </div>
              <BotChart
                bot={bot}
                trades={tradesMap[bot.id] ?? []}
                activeTimeframe={activeTimeframe}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
