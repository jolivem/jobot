"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { logout } from "@/lib/api";

export default function Navbar() {
  const router = useRouter();
  const pathname = usePathname();
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    setLoggedIn(!!localStorage.getItem("access_token"));
  }, [pathname]);

  const handleLogout = async () => {
    const refreshToken = localStorage.getItem("refresh_token");
    if (refreshToken) {
      await logout(refreshToken).catch(() => {});
    }
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    setLoggedIn(false);
    router.push("/login");
  };

  return (
    <nav className="border-b border-gray-200 dark:border-gray-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          <Link href={loggedIn ? "/dashboard" : "/"} className="text-xl font-bold">
            Jobot
          </Link>
          <div className="flex gap-4 items-center">
            {loggedIn ? (
              <>
                <Link
                  href="/dashboard"
                  className="px-4 py-2 text-sm font-medium hover:text-gray-600 dark:hover:text-gray-300"
                >
                  Dashboard
                </Link>
                <Link
                  href="/bots"
                  className="px-4 py-2 text-sm font-medium hover:text-gray-600 dark:hover:text-gray-300"
                >
                  Bots
                </Link>
                <Link
                  href="/trades"
                  className="px-4 py-2 text-sm font-medium hover:text-gray-600 dark:hover:text-gray-300"
                >
                  Trades
                </Link>
                <Link
                  href="/settings"
                  className="px-4 py-2 text-sm font-medium hover:text-gray-600 dark:hover:text-gray-300"
                >
                  Settings
                </Link>
                <button
                  onClick={handleLogout}
                  className="px-4 py-2 text-sm font-medium text-red-600 hover:text-red-700"
                >
                  Logout
                </button>
              </>
            ) : (
              <>
                <Link
                  href="/login"
                  className="px-4 py-2 text-sm font-medium hover:text-gray-600 dark:hover:text-gray-300"
                >
                  Login
                </Link>
                <Link
                  href="/register"
                  className="px-4 py-2 text-sm font-medium bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  Sign Up
                </Link>
              </>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}
