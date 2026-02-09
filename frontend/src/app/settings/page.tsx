"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getMe, updateMe, verifyBinanceKeys, UserResponse, UserUpdateRequest } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

export default function SettingsPage() {
  const router = useRouter();
  const { isAuthenticated, loading: authLoading, refreshUser } = useAuth();
  const [user, setUser] = useState<UserResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const [form, setForm] = useState({
    email: "",
    username: "",
    first_name: "",
    last_name: "",
    binance_api_key: "",
    binance_api_secret: "",
  });

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/login");
      return;
    }
    if (authLoading || !isAuthenticated) return;

    getMe()
      .then((u) => {
        setUser(u);
        setForm({
          email: u.email,
          username: u.username || "",
          first_name: u.first_name || "",
          last_name: u.last_name || "",
          binance_api_key: "",
          binance_api_secret: "",
        });
      })
      .catch(() => router.push("/login"))
      .finally(() => setLoading(false));
  }, [authLoading, isAuthenticated, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setMessage("");
    setSaving(true);

    const data: UserUpdateRequest = {};
    if (form.email !== user?.email) data.email = form.email;
    if (form.username !== (user?.username || "")) data.username = form.username || undefined;
    if (form.first_name !== (user?.first_name || "")) data.first_name = form.first_name || undefined;
    if (form.last_name !== (user?.last_name || "")) data.last_name = form.last_name || undefined;
    if (form.binance_api_key) data.binance_api_key = form.binance_api_key;
    if (form.binance_api_secret) data.binance_api_secret = form.binance_api_secret;

    if (Object.keys(data).length === 0) {
      setMessage("No changes to save.");
      setSaving(false);
      return;
    }

    try {
      const updated = await updateMe(data);
      setUser(updated);
      await refreshUser();
      setForm((prev) => ({
        ...prev,
        binance_api_key: "",
        binance_api_secret: "",
      }));
      setMessage("Settings saved successfully.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  const handleVerifyBinance = async () => {
    setError("");
    setMessage("");
    setVerifying(true);

    try {
      await verifyBinanceKeys();
      setMessage("Binance API keys are valid!");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to verify Binance keys");
    } finally {
      setVerifying(false);
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

  const inputClass =
    "w-full px-4 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900 focus:ring-2 focus:ring-blue-500 focus:border-transparent";

  return (
    <div className="max-w-2xl mx-auto px-4 py-10">
      <h1 className="text-3xl font-bold mb-8">Settings</h1>

      <form onSubmit={handleSubmit} className="space-y-6">
        {error && (
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 px-4 py-3 rounded-lg">
            {error}
          </div>
        )}
        {message && (
          <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 text-green-600 dark:text-green-400 px-4 py-3 rounded-lg">
            {message}
          </div>
        )}

        <div className="space-y-4">
          <h2 className="text-lg font-semibold border-b border-gray-200 dark:border-gray-800 pb-2">
            Profile
          </h2>

          <div>
            <label htmlFor="email" className="block text-sm font-medium mb-1">Email</label>
            <input
              id="email"
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              className={inputClass}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="first_name" className="block text-sm font-medium mb-1">First Name</label>
              <input
                id="first_name"
                type="text"
                value={form.first_name}
                onChange={(e) => setForm({ ...form, first_name: e.target.value })}
                className={inputClass}
              />
            </div>
            <div>
              <label htmlFor="last_name" className="block text-sm font-medium mb-1">Last Name</label>
              <input
                id="last_name"
                type="text"
                value={form.last_name}
                onChange={(e) => setForm({ ...form, last_name: e.target.value })}
                className={inputClass}
              />
            </div>
          </div>

          <div>
            <label htmlFor="username" className="block text-sm font-medium mb-1">Username</label>
            <input
              id="username"
              type="text"
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
              className={inputClass}
            />
          </div>
        </div>

        <div className="space-y-4">
          <h2 className="text-lg font-semibold border-b border-gray-200 dark:border-gray-800 pb-2">
            Binance API Keys
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Current key: {user.binance_api_key || "Not configured"}
          </p>

          <div>
            <label htmlFor="binance_api_key" className="block text-sm font-medium mb-1">
              API Key
            </label>
            <input
              id="binance_api_key"
              type="text"
              value={form.binance_api_key}
              onChange={(e) => setForm({ ...form, binance_api_key: e.target.value })}
              className={inputClass}
              placeholder="Leave empty to keep current"
            />
          </div>

          <div>
            <label htmlFor="binance_api_secret" className="block text-sm font-medium mb-1">
              API Secret
            </label>
            <input
              id="binance_api_secret"
              type="password"
              value={form.binance_api_secret}
              onChange={(e) => setForm({ ...form, binance_api_secret: e.target.value })}
              className={inputClass}
              placeholder="Leave empty to keep current"
            />
          </div>

          {user.binance_api_key && (
            <button
              type="button"
              onClick={handleVerifyBinance}
              disabled={verifying}
              className="w-full py-2 px-4 border border-gray-300 dark:border-gray-700 font-medium rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {verifying ? "Verifying..." : "Verify Binance Keys"}
            </button>
          )}
        </div>

        <button
          type="submit"
          disabled={saving}
          className="w-full py-3 px-4 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {saving ? "Saving..." : "Save Settings"}
        </button>
      </form>
    </div>
  );
}
