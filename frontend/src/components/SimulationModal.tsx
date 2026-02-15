"use client";

import { useState } from "react";
import {
  simulateBot,
  updateBot,
  SimulationResponse,
  BacktestMetrics,
  TradingBot,
} from "@/lib/api";

interface Props {
  bot: TradingBot;
  onClose: () => void;
  onApply: (updated: TradingBot) => void;
}

function MetricRow({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex justify-between text-sm">
      <span className="text-gray-500 dark:text-gray-400">{label}</span>
      <span className={`font-medium ${color ?? ""}`}>{value}</span>
    </div>
  );
}

function pnlColor(val: number) {
  return val >= 0
    ? "text-green-600 dark:text-green-400"
    : "text-red-600 dark:text-red-400";
}

function MetricsCard({ title, m }: { title: string; m: BacktestMetrics }) {
  return (
    <div className="p-4 rounded-lg bg-gray-50 dark:bg-gray-900/50 space-y-2">
      <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
        {title}
      </h4>
      <MetricRow label="P&L" value={`${m.total_pnl >= 0 ? "+" : ""}${m.total_pnl.toFixed(4)} $`} color={pnlColor(m.total_pnl)} />
      <MetricRow label="P&L %" value={`${m.total_pnl_pct >= 0 ? "+" : ""}${m.total_pnl_pct.toFixed(2)}%`} color={pnlColor(m.total_pnl_pct)} />
      <MetricRow label="Trades" value={`${m.num_buys} buys / ${m.num_sells} sells`} />
      <MetricRow label="Win Rate" value={`${(m.win_rate * 100).toFixed(1)}%`} />
      <MetricRow label="Max Drawdown" value={`${(m.max_drawdown * 100).toFixed(2)}%`} />
      <MetricRow label="Sharpe" value={m.sharpe_ratio.toFixed(2)} />
      {m.final_open_positions > 0 && (
        <MetricRow label="Open Positions" value={String(m.final_open_positions)} />
      )}
    </div>
  );
}

export default function SimulationModal({ bot, onClose, onApply }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<SimulationResponse | null>(null);
  const [applying, setApplying] = useState(false);

  const runSimulation = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await simulateBot(bot.id, { interval: "1m", limit: 10080 });
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Simulation failed");
    } finally {
      setLoading(false);
    }
  };

  const applyParams = async () => {
    if (!result) return;
    setApplying(true);
    try {
      const best = result.best_params;
      const updated = await updateBot(bot.id, {
        min_price: best.min_price,
        max_price: best.max_price,
        grid_levels: best.grid_levels,
        sell_percentage: best.sell_percentage,
      });
      onApply(updated);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to apply parameters");
    } finally {
      setApplying(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white dark:bg-gray-950 border border-gray-200 dark:border-gray-800 rounded-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto p-6 space-y-4">
        {/* Header */}
        <div className="flex justify-between items-center">
          <h2 className="text-xl font-bold">Simulate {bot.symbol}</h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 text-2xl leading-none"
          >
            &times;
          </button>
        </div>

        {error && (
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 px-4 py-3 rounded-lg text-sm">
            {error}
          </div>
        )}

        {!result && !loading && (
          <div className="text-center py-8 space-y-4">
            <p className="text-gray-500 dark:text-gray-400">
              Run a backtest optimization on 7 days of historical data (1min candles, 10 080 points) to find the best grid parameters for {bot.symbol}.
            </p>
            <button
              onClick={runSimulation}
              className="px-6 py-3 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 transition"
            >
              Run Optimization
            </button>
          </div>
        )}

        {loading && (
          <div className="text-center py-12 space-y-3">
            <div className="inline-block h-8 w-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
            <p className="text-gray-500 dark:text-gray-400">
              Analyzing parameter combinations...
            </p>
          </div>
        )}

        {result && (
          <>
            {/* Best Parameters */}
            <div className="p-4 rounded-lg bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800">
              <h3 className="text-sm font-semibold text-blue-700 dark:text-blue-300 mb-3">
                Best Parameters
              </h3>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <span className="text-gray-500 dark:text-gray-400">Min Price</span>
                  <p className="font-bold">${result.best_params.min_price.toLocaleString()}</p>
                </div>
                <div>
                  <span className="text-gray-500 dark:text-gray-400">Max Price</span>
                  <p className="font-bold">${result.best_params.max_price.toLocaleString()}</p>
                </div>
                <div>
                  <span className="text-gray-500 dark:text-gray-400">Grid Levels</span>
                  <p className="font-bold">{result.best_params.grid_levels}</p>
                </div>
                <div>
                  <span className="text-gray-500 dark:text-gray-400">Sell %</span>
                  <p className="font-bold">{result.best_params.sell_percentage}%</p>
                </div>
              </div>
            </div>

            {/* Train vs Test Results */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <MetricsCard title={`Train (${result.train_size} candles)`} m={result.best_params} />
              <MetricsCard title={`Test (${result.test_size} candles)`} m={result.test_result} />
            </div>

            {/* Top 10 Results */}
            {result.top_results.length > 1 && (
              <div>
                <h3 className="text-sm font-semibold mb-2">Top Results</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-left text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-800">
                        <th className="py-2 pr-2">#</th>
                        <th className="py-2 pr-2">Min</th>
                        <th className="py-2 pr-2">Max</th>
                        <th className="py-2 pr-2">Levels</th>
                        <th className="py-2 pr-2">Sell%</th>
                        <th className="py-2 pr-2">P&L%</th>
                        <th className="py-2 pr-2">Win</th>
                        <th className="py-2">Trades</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.top_results.map((r, i) => (
                        <tr key={i} className="border-b border-gray-100 dark:border-gray-900">
                          <td className="py-1.5 pr-2 text-gray-400">{i + 1}</td>
                          <td className="py-1.5 pr-2">${r.min_price.toLocaleString()}</td>
                          <td className="py-1.5 pr-2">${r.max_price.toLocaleString()}</td>
                          <td className="py-1.5 pr-2">{r.grid_levels}</td>
                          <td className="py-1.5 pr-2">{r.sell_percentage}%</td>
                          <td className={`py-1.5 pr-2 font-medium ${pnlColor(r.total_pnl_pct)}`}>
                            {r.total_pnl_pct >= 0 ? "+" : ""}{r.total_pnl_pct.toFixed(2)}%
                          </td>
                          <td className="py-1.5 pr-2">{(r.win_rate * 100).toFixed(0)}%</td>
                          <td className="py-1.5">{r.num_trades}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            <p className="text-xs text-gray-400">
              Computed in {result.computed_in_ms}ms using {result.kline_interval} candles
            </p>

            {/* Actions */}
            <div className="flex gap-3">
              <button
                onClick={applyParams}
                disabled={applying}
                className="flex-1 py-2.5 px-4 bg-green-600 text-white font-medium rounded-lg hover:bg-green-700 transition disabled:opacity-50"
              >
                {applying ? "Applying..." : "Apply Best Parameters"}
              </button>
              <button
                onClick={onClose}
                className="flex-1 py-2.5 px-4 border border-gray-300 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition"
              >
                Close
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
