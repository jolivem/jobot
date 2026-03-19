"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { verifyEmail } from "@/lib/api";

export default function VerifyEmailPage() {
  const params = useParams();
  const token = params.token as string;
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [error, setError] = useState("");

  useEffect(() => {
    async function verify() {
      try {
        await verifyEmail(token);
        setStatus("success");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Verification failed");
        setStatus("error");
      }
    }

    if (token) {
      verify();
    }
  }, [token]);

  if (status === "loading") {
    return (
      <div className="flex flex-col items-center justify-center min-h-[calc(100vh-4rem)]">
        <div className="max-w-md w-full mx-auto px-4 text-center">
          <div className="inline-block h-10 w-10 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin mb-4" />
          <h2 className="text-xl font-semibold">Verifying your email...</h2>
        </div>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="flex flex-col items-center justify-center min-h-[calc(100vh-4rem)]">
        <div className="max-w-md w-full mx-auto px-4">
          <div className="bg-gradient-to-br from-red-50 to-rose-50 dark:from-red-900/20 dark:to-rose-900/20 border border-red-200 dark:border-red-800 rounded-xl p-6 text-center">
            <div className="text-4xl mb-4">&#10060;</div>
            <h2 className="text-xl font-semibold mb-2">Verification Failed</h2>
            <p className="text-gray-600 dark:text-gray-400 mb-4">
              {error}
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-500">
              The link may have expired or already been used.
            </p>
            <Link
              href="/register"
              className="inline-block mt-6 text-emerald-600 hover:text-emerald-700 dark:text-emerald-400 font-medium"
            >
              Try registering again
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-4rem)]">
      <div className="max-w-md w-full mx-auto px-4">
        <div className="bg-gradient-to-br from-emerald-50 to-teal-50 dark:from-emerald-900/20 dark:to-teal-900/20 border border-emerald-200 dark:border-emerald-800 rounded-xl p-6 text-center">
          <div className="text-4xl mb-4">&#10004;</div>
          <h2 className="text-xl font-semibold mb-2">Email Verified!</h2>
          <p className="text-gray-600 dark:text-gray-400">
            Your account has been verified. You can now login.
          </p>
          <Link
            href="/login"
            className="inline-block mt-6 px-6 py-2 bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-medium rounded-lg hover:from-emerald-600 hover:to-teal-700 transition shadow-lg shadow-emerald-500/25"
          >
            Go to Login
          </Link>
        </div>
      </div>
    </div>
  );
}
