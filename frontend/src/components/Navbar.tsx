"use client";

import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";

export default function Navbar() {
  const { isAuthenticated, logout } = useAuth();

  return (
    <nav className="border-b border-gray-200 dark:border-gray-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          <Link href={isAuthenticated ? "/dashboard" : "/"} className="text-xl font-bold">
            Jobot
          </Link>
          <div className="flex gap-4 items-center">
            {isAuthenticated ? (
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
                  href="/screening"
                  className="px-4 py-2 text-sm font-medium hover:text-gray-600 dark:hover:text-gray-300"
                >
                  Screening
                </Link>
                <Link
                  href="/settings"
                  className="px-4 py-2 text-sm font-medium hover:text-gray-600 dark:hover:text-gray-300"
                >
                  Settings
                </Link>
                <button
                  onClick={logout}
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
