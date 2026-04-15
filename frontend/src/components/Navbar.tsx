"use client";

import { useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";

export default function Navbar() {
  const { isAuthenticated, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);

  const close = () => setMenuOpen(false);

  const linkClass =
    "px-4 py-2 text-sm font-medium text-gray-600 dark:text-gray-300 hover:text-emerald-600 dark:hover:text-emerald-400 transition";
  const mobileLinkClass =
    "block px-3 py-2 rounded-lg text-sm font-medium hover:bg-emerald-50 dark:hover:bg-emerald-900/20 hover:text-emerald-600 dark:hover:text-emerald-400 transition";

  return (
    <nav className="border-b border-gray-200 dark:border-gray-800 bg-white/80 dark:bg-gray-950/80 backdrop-blur-sm sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          <Link
            href={isAuthenticated ? "/dashboard" : "/"}
            className="flex items-center gap-2 text-xl font-bold bg-gradient-to-r from-emerald-500 to-teal-600 bg-clip-text text-transparent"
            onClick={close}
          >
            <Image src="/icon.svg" alt="Jobot" width={32} height={32} />
            Jobot
          </Link>

          {/* Desktop menu */}
          <div className="hidden sm:flex gap-1 items-center">
            {isAuthenticated ? (
              <>
                <Link href="/dashboard" className={linkClass}>Dashboard</Link>
                <Link href="/bots" className={linkClass}>Bots</Link>
                <Link href="/charts" className={linkClass}>Charts</Link>
                <Link href="/trades" className={linkClass}>Trades</Link>
                <Link href="/history" className={linkClass}>History</Link>
                <Link href="/settings" className={linkClass}>Settings</Link>
                <button onClick={logout} className="ml-2 px-4 py-2 text-sm font-medium text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition">Logout</button>
              </>
            ) : (
              <>
                <Link href="/login" className={linkClass}>Login</Link>
                <Link href="/register" className="px-4 py-2 text-sm font-medium bg-gradient-to-r from-emerald-500 to-teal-600 text-white rounded-lg hover:from-emerald-600 hover:to-teal-700 transition">Sign Up</Link>
              </>
            )}
          </div>

          {/* Burger button (mobile) */}
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="sm:hidden p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition"
            aria-label="Menu"
          >
            {menuOpen ? (
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            ) : (
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            )}
          </button>
        </div>
      </div>

      {/* Mobile menu */}
      {menuOpen && (
        <div className="sm:hidden border-t border-gray-200 dark:border-gray-800 px-4 py-3 space-y-1 bg-white dark:bg-gray-950">
          {isAuthenticated ? (
            <>
              <Link href="/dashboard" onClick={close} className={mobileLinkClass}>Dashboard</Link>
              <Link href="/bots" onClick={close} className={mobileLinkClass}>Bots</Link>
              <Link href="/charts" onClick={close} className={mobileLinkClass}>Charts</Link>
              <Link href="/trades" onClick={close} className={mobileLinkClass}>Trades</Link>
              <Link href="/history" onClick={close} className={mobileLinkClass}>History</Link>
              <Link href="/settings" onClick={close} className={mobileLinkClass}>Settings</Link>
              <button onClick={() => { logout(); close(); }} className="block w-full text-left px-3 py-2 rounded-lg text-sm font-medium text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition">Logout</button>
            </>
          ) : (
            <>
              <Link href="/login" onClick={close} className={mobileLinkClass}>Login</Link>
              <Link href="/register" onClick={close} className="block px-3 py-2 rounded-lg text-sm font-medium bg-gradient-to-r from-emerald-500 to-teal-600 text-white hover:from-emerald-600 hover:to-teal-700">Sign Up</Link>
            </>
          )}
        </div>
      )}
    </nav>
  );
}
