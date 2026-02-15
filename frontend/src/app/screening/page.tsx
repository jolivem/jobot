"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  launchScreening,
  getScreeningStatus,
  ScreeningStatus,
  ScreeningSymbolResult,
} from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

type SortKey = keyof ScreeningSymbolResult;

export default function ScreeningPage() {
  const router = useRouter();
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [taskId, setTaskId] = useState<string | null>(null);
  const [status, setStatus] = useState<ScreeningStatus | null>(null);
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("best_pnl_pct");
  const [sortDesc, setSortDesc] = useState(true);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [authLoading, isAuthenticated, router]);

  // Restore task_id from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem("screening_task_id");
    if (saved) {
      setTaskId(saved);
    }
  }, []);

  // Poll for results when taskId is set and status is not final
  useEffect(() => {
    if (!taskId) return;
    if (status?.status === "completed" || status?.status === "failed") return;

    const poll = async () => {
      try {
        const s = await getScreeningStatus(taskId);
        setStatus(s);
        if (s.status === "completed" || s.status === "failed") {
          if (pollingRef.current) {
            clearInterval(pollingRef.current);
            pollingRef.current = null;
          }
        }
      } catch {
        // Task may not be available yet
      }
    };

    poll();
    pollingRef.current = setInterval(poll, 3000);

    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, [taskId, status?.status]);

  const handleLaunch = async () => {
    setLaunching(true);
    setError("");
    setStatus(null);
    try {
      const res = await launchScreening();
      setTaskId(res.task_id);
      localStorage.setItem("screening_task_id", res.task_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to launch screening");
    } finally {
      setLaunching(false);
    }
  };

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDesc(!sortDesc);
    } else {
      setSortKey(key);
      setSortDesc(true);
    }
  };

  const sortedResults = status?.results
    ? [...status.results].sort((a, b) => {
        const av = a[sortKey] as number;
        const bv = b[sortKey] as number;
        return sortDesc ? bv - av : av - bv;
      })
    : [];

  const SortHeader = ({ label, field }: { label: string; field: SortKey }) => (
    <th
      className="py-2 pr-3 cursor-pointer hover:text-gray-700 dark:hover:text-gray-200 select-none"
      onClick={() => handleSort(field)}
    >
      {label}
      {sortKey === field && (
        <span className="ml-1">{sortDesc ? "\u25BC" : "\u25B2"}</span>
      )}
    </th>
  );

  const pnlColor = (val: number) =>
    val >= 0
      ? "text-green-600 dark:text-green-400"
      : "text-red-600 dark:text-red-400";

  if (authLoading) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-4rem)]">
        <p className="text-gray-500">Loading...</p>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold">Market Screening</h1>
        <button
          onClick={handleLaunch}
          disabled={launching || (status?.status === "running")}
          className="px-4 py-2 text-sm font-medium bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {launching
            ? "Launching..."
            : status?.status === "running"
              ? "Screening in progress..."
              : "Launch Screening"}
        </button>
      </div>

      {error && (
        <div className="mb-6 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      {/* Progress Bar */}
      {status && (status.status === "running" || status.status === "pending") && (
        <div className="mb-6 p-4 border border-gray-200 dark:border-gray-800 rounded-xl space-y-3">
          <div className="flex justify-between text-sm">
            <span className="text-gray-500 dark:text-gray-400">
              {status.processed_symbols} / {status.total_symbols} symbols
            </span>
            <span className="font-medium">{status.progress}%</span>
          </div>
          <div className="w-full bg-gray-200 dark:bg-gray-800 rounded-full h-2.5">
            <div
              className="bg-blue-600 h-2.5 rounded-full transition-all duration-500"
              style={{ width: `${status.progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Completed status */}
      {status?.status === "completed" && (
        <div className="mb-6 p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 text-green-700 dark:text-green-400 rounded-lg text-sm">
          Screening completed: {status.results.length} symbols analyzed
        </div>
      )}

      {/* Results Table */}
      {sortedResults.length > 0 && (
        <div className="border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900/50">
                  <th className="py-2 pl-4 pr-3">#</th>
                  <SortHeader label="Symbol" field="symbol" />
                  <SortHeader label="P&L% (train)" field="best_pnl_pct" />
                  <SortHeader label="P&L% (test)" field="test_pnl_pct" />
                  <SortHeader label="Trades" field="num_trades" />
                  <SortHeader label="Win Rate" field="win_rate" />
                  <SortHeader label="Drawdown" field="max_drawdown" />
                  <SortHeader label="Sharpe" field="sharpe_ratio" />
                  <th className="py-2 pr-3">Best Params</th>
                </tr>
              </thead>
              <tbody>
                {sortedResults.map((r, i) => (
                  <tr
                    key={r.symbol}
                    className="border-b border-gray-100 dark:border-gray-900 hover:bg-gray-50 dark:hover:bg-gray-900/30"
                  >
                    <td className="py-2.5 pl-4 pr-3 text-gray-400">{i + 1}</td>
                    <td className="py-2.5 pr-3 font-medium">{r.symbol}</td>
                    <td className={`py-2.5 pr-3 font-medium ${pnlColor(r.best_pnl_pct)}`}>
                      {r.best_pnl_pct >= 0 ? "+" : ""}{r.best_pnl_pct.toFixed(2)}%
                    </td>
                    <td className={`py-2.5 pr-3 font-medium ${pnlColor(r.test_pnl_pct)}`}>
                      {r.test_pnl_pct >= 0 ? "+" : ""}{r.test_pnl_pct.toFixed(2)}%
                    </td>
                    <td className="py-2.5 pr-3">{r.num_trades}</td>
                    <td className="py-2.5 pr-3">{(r.win_rate * 100).toFixed(0)}%</td>
                    <td className="py-2.5 pr-3">{(r.max_drawdown * 100).toFixed(1)}%</td>
                    <td className="py-2.5 pr-3">{r.sharpe_ratio.toFixed(1)}</td>
                    <td className="py-2.5 pr-3 text-xs text-gray-500 dark:text-gray-400">
                      {r.best_grid_levels}L / {r.best_sell_percentage}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!status && !taskId && (
        <div className="text-center py-20 border border-gray-200 dark:border-gray-800 rounded-xl">
          <p className="text-gray-500 dark:text-gray-400 text-lg mb-2">
            No screening results yet.
          </p>
          <p className="text-gray-400 dark:text-gray-500 text-sm">
            Launch a screening to analyze all USDC pairs on Binance and find the best grid trading candidates.
          </p>
        </div>
      )}
    </div>
  );
}
