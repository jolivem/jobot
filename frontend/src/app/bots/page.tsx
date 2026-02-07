"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { listBots, createBot, TradingBot, TradingBotCreate } from "@/lib/api";

const emptyForm: TradingBotCreate = {
  symbol: "",
  min_price: 0,
  max_price: 0,
  total_amount: 0,
  buy_percentage: 0,
  sell_percentage: 0,
};

export default function BotsPage() {
  const router = useRouter();
  const [bots, setBots] = useState<TradingBot[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState<TradingBotCreate>({ ...emptyForm });

  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;

  useEffect(() => {
    if (!token) {
      router.push("/login");
      return;
    }
    listBots(token)
      .then(setBots)
      .catch(() => router.push("/login"))
      .finally(() => setLoading(false));
  }, [token, router]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;
    setError("");
    setSaving(true);

    try {
      const bot = await createBot(token, form);
      setBots((prev) => [...prev, bot]);
      setForm({ ...emptyForm });
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
    "w-full px-4 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900 focus:ring-2 focus:ring-blue-500 focus:border-transparent";

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

          <div>
            <label htmlFor="symbol" className="block text-sm font-medium mb-1">
              Symbol
            </label>
            <input
              id="symbol"
              type="text"
              value={form.symbol}
              onChange={(e) => setForm({ ...form, symbol: e.target.value.toUpperCase() })}
              className={inputClass}
              placeholder="BTCUSDT"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="min_price" className="block text-sm font-medium mb-1">
                Min Price ($)
              </label>
              <input
                id="min_price"
                type="number"
                step="any"
                value={form.min_price || ""}
                onChange={(e) => setForm({ ...form, min_price: parseFloat(e.target.value) || 0 })}
                className={inputClass}
                required
              />
            </div>
            <div>
              <label htmlFor="max_price" className="block text-sm font-medium mb-1">
                Max Price ($)
              </label>
              <input
                id="max_price"
                type="number"
                step="any"
                value={form.max_price || ""}
                onChange={(e) => setForm({ ...form, max_price: parseFloat(e.target.value) || 0 })}
                className={inputClass}
                required
              />
            </div>
          </div>

          <div>
            <label htmlFor="total_amount" className="block text-sm font-medium mb-1">
              Total Amount ($)
            </label>
            <input
              id="total_amount"
              type="number"
              step="any"
              value={form.total_amount || ""}
              onChange={(e) => setForm({ ...form, total_amount: parseFloat(e.target.value) || 0 })}
              className={inputClass}
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="buy_percentage" className="block text-sm font-medium mb-1">
                Buy Percentage (%)
              </label>
              <input
                id="buy_percentage"
                type="number"
                step="any"
                min="0"
                max="100"
                value={form.buy_percentage || ""}
                onChange={(e) => setForm({ ...form, buy_percentage: parseFloat(e.target.value) || 0 })}
                className={inputClass}
                required
              />
            </div>
            <div>
              <label htmlFor="sell_percentage" className="block text-sm font-medium mb-1">
                Sell Percentage (%)
              </label>
              <input
                id="sell_percentage"
                type="number"
                step="any"
                min="0"
                max="100"
                value={form.sell_percentage || ""}
                onChange={(e) => setForm({ ...form, sell_percentage: parseFloat(e.target.value) || 0 })}
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

              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>
                  <span className="text-gray-500 dark:text-gray-400">Min Price</span>
                  <p className="font-medium">${bot.min_price.toLocaleString()}</p>
                </div>
                <div>
                  <span className="text-gray-500 dark:text-gray-400">Max Price</span>
                  <p className="font-medium">${bot.max_price.toLocaleString()}</p>
                </div>
                <div>
                  <span className="text-gray-500 dark:text-gray-400">Amount</span>
                  <p className="font-medium">${bot.total_amount.toLocaleString()}</p>
                </div>
                <div>
                  <span className="text-gray-500 dark:text-gray-400">Buy %</span>
                  <p className="font-medium">{bot.buy_percentage}%</p>
                </div>
                <div>
                  <span className="text-gray-500 dark:text-gray-400">Sell %</span>
                  <p className="font-medium">{bot.sell_percentage}%</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
