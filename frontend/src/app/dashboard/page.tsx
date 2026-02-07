"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getMe, UserResponse } from "@/lib/api";

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<UserResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      router.push("/login");
      return;
    }

    getMe(token)
      .then(setUser)
      .catch(() => {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        router.push("/login");
      })
      .finally(() => setLoading(false));
  }, [router]);

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
    </div>
  );
}
