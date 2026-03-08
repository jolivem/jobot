"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { fetchBnbBalance, convertToBnb } from "@/lib/api";

export default function DashboardPage() {
  const router = useRouter();
  const { user, isAuthenticated, loading } = useAuth();

  const [bnbFree, setBnbFree] = useState<number | null>(null);
  const [bnbLocked, setBnbLocked] = useState<number | null>(null);
  const [bnbLoading, setBnbLoading] = useState(false);

  const [convertAmount, setConvertAmount] = useState("");
  const [converting, setConverting] = useState(false);
  const [convertResult, setConvertResult] = useState<string | null>(null);
  const [convertError, setConvertError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && !isAuthenticated) router.push("/login");
  }, [loading, isAuthenticated, router]);

  useEffect(() => {
    if (user?.binance_api_key) {
      setBnbLoading(true);
      fetchBnbBalance()
        .then((data) => {
          setBnbFree(data.free);
          setBnbLocked(data.locked);
        })
        .catch(() => {
          setBnbFree(null);
          setBnbLocked(null);
        })
        .finally(() => setBnbLoading(false));
    }
  }, [user]);

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
      // Refresh balance
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

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="p-6 border border-gray-200 dark:border-gray-800 rounded-xl">
          <h2 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">
            Email
          </h2>
          <p className="text-lg font-semibold">{user.email}</p>
        </div>

        <div className="p-6 border border-gray-200 dark:border-gray-800 rounded-xl">
          <h2 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">
            Role
          </h2>
          <p className="text-lg font-semibold capitalize">{user.role}</p>
        </div>

        <div className="p-6 border border-gray-200 dark:border-gray-800 rounded-xl">
          <h2 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">
            Binance API
          </h2>
          <p className="text-lg font-semibold">
            {user.binance_api_key ? "Connected" : "Not configured"}
          </p>
        </div>
      </div>

      {/* BNB Section */}
      {user.binance_api_key && (
        <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* BNB Balance */}
          <div className="p-6 border border-gray-200 dark:border-gray-800 rounded-xl">
            <h2 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">
              BNB disponible
            </h2>
            {bnbLoading ? (
              <p className="text-gray-400">Chargement...</p>
            ) : bnbFree !== null ? (
              <div>
                <p className="text-2xl font-bold">{bnbFree.toFixed(6)} BNB</p>
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
          <div className="p-6 border border-gray-200 dark:border-gray-800 rounded-xl">
            <h2 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-3">
              Convertir USDC en BNB
            </h2>
            <div className="flex gap-3">
              <input
                type="number"
                min="0"
                step="0.01"
                placeholder="Montant USDC"
                value={convertAmount}
                onChange={(e) => setConvertAmount(e.target.value)}
                className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-transparent focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                onClick={handleConvert}
                disabled={converting || !convertAmount}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
              >
                {converting ? "..." : "Acheter BNB"}
              </button>
            </div>
            {convertResult && (
              <p className="mt-2 text-sm text-green-600 dark:text-green-400">
                {convertResult}
              </p>
            )}
            {convertError && (
              <p className="mt-2 text-sm text-red-600 dark:text-red-400">
                {convertError}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
