import Link from "next/link";

export default function Home() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-4rem)]">
      <div className="max-w-4xl mx-auto px-4 text-center">
        <h1 className="text-5xl font-bold mb-6">
          <span className="bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500 bg-clip-text text-transparent">
            Automated Crypto Trading
          </span>
        </h1>
        <p className="text-xl text-gray-600 dark:text-gray-400 mb-8 max-w-2xl mx-auto">
          Jobot is your intelligent trading assistant. Connect your Binance account
          and let our bots trade for you 24/7 based on your strategy.
        </p>
        <div className="flex gap-4 justify-center">
          <Link
            href="/register"
            className="px-8 py-3 text-lg font-medium bg-gradient-to-r from-emerald-500 to-teal-600 text-white rounded-lg hover:from-emerald-600 hover:to-teal-700 transition shadow-lg shadow-emerald-500/25"
          >
            Get Started
          </Link>
          <Link
            href="/login"
            className="px-8 py-3 text-lg font-medium border border-gray-300 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-900 transition"
          >
            Login
          </Link>
        </div>

        <div className="mt-20 grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="p-6 rounded-xl bg-gradient-to-br from-amber-500/10 to-orange-500/5 border border-amber-500/20">
            <div className="text-3xl mb-4">&#9889;</div>
            <h3 className="text-lg font-semibold mb-2 text-amber-700 dark:text-amber-400">Real-time Trading</h3>
            <p className="text-gray-600 dark:text-gray-400">
              Bots monitor prices every second and execute trades instantly.
            </p>
          </div>
          <div className="p-6 rounded-xl bg-gradient-to-br from-blue-500/10 to-indigo-500/5 border border-blue-500/20">
            <div className="text-3xl mb-4">&#128274;</div>
            <h3 className="text-lg font-semibold mb-2 text-blue-700 dark:text-blue-400">Secure</h3>
            <p className="text-gray-600 dark:text-gray-400">
              Your API keys are encrypted. We never have access to withdraw funds.
            </p>
          </div>
          <div className="p-6 rounded-xl bg-gradient-to-br from-emerald-500/10 to-teal-500/5 border border-emerald-500/20">
            <div className="text-3xl mb-4">&#128200;</div>
            <h3 className="text-lg font-semibold mb-2 text-emerald-700 dark:text-emerald-400">Track Performance</h3>
            <p className="text-gray-600 dark:text-gray-400">
              View your trade history and monitor bot performance in real-time.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
