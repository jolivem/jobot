import Link from "next/link";

export default function Home() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-4rem)]">
      <div className="max-w-4xl mx-auto px-4 text-center">
        <h1 className="text-5xl font-bold mb-6">
          Automated Crypto Trading
        </h1>
        <p className="text-xl text-gray-600 dark:text-gray-400 mb-8 max-w-2xl mx-auto">
          Jobot is your intelligent trading assistant. Connect your Binance account
          and let our bots trade for you 24/7 based on your strategy.
        </p>
        <div className="flex gap-4 justify-center">
          <Link
            href="/register"
            className="px-8 py-3 text-lg font-medium bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
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
          <div className="p-6 border border-gray-200 dark:border-gray-800 rounded-xl">
            <div className="text-3xl mb-4">&#9889;</div>
            <h3 className="text-lg font-semibold mb-2">Real-time Trading</h3>
            <p className="text-gray-600 dark:text-gray-400">
              Bots monitor prices every second and execute trades instantly.
            </p>
          </div>
          <div className="p-6 border border-gray-200 dark:border-gray-800 rounded-xl">
            <div className="text-3xl mb-4">&#128274;</div>
            <h3 className="text-lg font-semibold mb-2">Secure</h3>
            <p className="text-gray-600 dark:text-gray-400">
              Your API keys are encrypted. We never have access to withdraw funds.
            </p>
          </div>
          <div className="p-6 border border-gray-200 dark:border-gray-800 rounded-xl">
            <div className="text-3xl mb-4">&#128200;</div>
            <h3 className="text-lg font-semibold mb-2">Track Performance</h3>
            <p className="text-gray-600 dark:text-gray-400">
              View your trade history and monitor bot performance in real-time.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
