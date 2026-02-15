const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ── Types ──────────────────────────────────────────────────────

export interface RegisterRequest {
  email: string;
  password: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface UserResponse {
  id: number;
  email: string;
  role: string;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  binance_api_key: string | null;
  binance_api_secret: string | null;
}

export interface ApiError {
  detail: string;
}

export interface UserUpdateRequest {
  email?: string;
  username?: string;
  first_name?: string;
  last_name?: string;
  password?: string;
  binance_api_key?: string;
  binance_api_secret?: string;
}

export interface TradingBot {
  id: number;
  user_id: number;
  symbol: string;
  is_active: number;
  max_price: number;
  min_price: number;
  total_amount: number;
  sell_percentage: number;
  grid_levels: number;
}

export interface TradingBotCreate {
  symbol: string;
  max_price: number;
  min_price: number;
  total_amount: number;
  sell_percentage: number;
  grid_levels: number;
}

export interface TradingBotUpdate {
  max_price?: number;
  min_price?: number;
  total_amount?: number;
  sell_percentage?: number;
  grid_levels?: number;
  is_active?: number;
}

export interface BotStats {
  bot_id: number;
  symbol: string;
  realized_profit: number;
  monthly_realized_profit: number;
  open_positions_count: number;
  open_positions_cost: number;
  current_price: number | null;
  open_positions_value: number | null;
}

export interface Trade {
  id: number;
  trading_bot_id: number;
  trade_type: string;
  price: number;
  quantity: number;
  created_at: string;
  symbol?: string;
}

// ── Helpers ────────────────────────────────────────────────────

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error = await response.json();
    let message = 'An error occurred';
    if (typeof error.detail === 'string') {
      message = error.detail;
    } else if (Array.isArray(error.detail)) {
      message = error.detail.map((e: { msg?: string }) => e.msg || String(e)).join(', ');
    }
    throw new Error(message);
  }
  return response.json();
}

/** Callback invoked when tokens are exhausted (refresh fails). Pages redirect to /login. */
let onAuthExpired: (() => void) | null = null;
export function setOnAuthExpired(cb: (() => void) | null) {
  onAuthExpired = cb;
}

async function refreshTokens(refreshToken: string): Promise<TokenResponse> {
  const response = await fetch(`${API_URL}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  return handleResponse<TokenResponse>(response);
}

// Deduplicate concurrent refresh attempts
let refreshPromise: Promise<string> | null = null;

/**
 * Authenticated fetch wrapper.
 * - Injects Authorization header from localStorage
 * - On 401, attempts to refresh the token and retries once
 */
async function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const accessToken = localStorage.getItem('access_token');
  if (!accessToken) {
    onAuthExpired?.();
    throw new Error('Not authenticated');
  }

  const doFetch = (token: string) => {
    const headers = new Headers(options.headers);
    headers.set('Authorization', `Bearer ${token}`);
    return fetch(url, { ...options, headers });
  };

  let response = await doFetch(accessToken);

  if (response.status === 401) {
    const rt = localStorage.getItem('refresh_token');
    if (!rt) {
      localStorage.removeItem('access_token');
      onAuthExpired?.();
      throw new Error('Session expired');
    }

    // Only one refresh at a time
    if (!refreshPromise) {
      refreshPromise = refreshTokens(rt)
        .then((tokens) => {
          localStorage.setItem('access_token', tokens.access_token);
          localStorage.setItem('refresh_token', tokens.refresh_token);
          return tokens.access_token;
        })
        .catch((err) => {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          onAuthExpired?.();
          throw err;
        })
        .finally(() => {
          refreshPromise = null;
        });
    }

    const newToken = await refreshPromise;
    response = await doFetch(newToken);
  }

  return response;
}

// ── Public (unauthenticated) endpoints ─────────────────────────

export async function register(data: RegisterRequest): Promise<UserResponse> {
  const response = await fetch(`${API_URL}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return handleResponse<UserResponse>(response);
}

export async function loginApi(data: LoginRequest): Promise<TokenResponse> {
  const response = await fetch(`${API_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return handleResponse<TokenResponse>(response);
}

export async function verifyEmail(token: string): Promise<{ verified: boolean }> {
  const response = await fetch(`${API_URL}/auth/verify/${token}`);
  return handleResponse<{ verified: boolean }>(response);
}

export async function logoutApi(refreshToken: string): Promise<void> {
  await fetch(`${API_URL}/auth/logout`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
}

export async function fetchUsdcSymbols(): Promise<string[]> {
  const response = await fetch(`${API_URL}/symbols/usdc`);
  const data = await handleResponse<{ symbols: string[] }>(response);
  return data.symbols;
}

// ── Authenticated endpoints (auto-refresh on 401) ─────────────

export async function getMe(): Promise<UserResponse> {
  const response = await authFetch(`${API_URL}/auth/me`);
  return handleResponse<UserResponse>(response);
}

export async function updateMe(data: UserUpdateRequest): Promise<UserResponse> {
  const response = await authFetch(`${API_URL}/auth/me`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return handleResponse<UserResponse>(response);
}

export async function verifyBinanceKeys(): Promise<{ valid: boolean }> {
  const response = await authFetch(`${API_URL}/auth/me/verify-binance`, {
    method: 'POST',
  });
  return handleResponse<{ valid: boolean }>(response);
}

export async function listBots(): Promise<TradingBot[]> {
  const response = await authFetch(`${API_URL}/trading-bots`);
  return handleResponse<TradingBot[]>(response);
}

export async function createBot(data: TradingBotCreate): Promise<TradingBot> {
  const response = await authFetch(`${API_URL}/trading-bots`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return handleResponse<TradingBot>(response);
}

export async function updateBot(botId: number, data: TradingBotUpdate): Promise<TradingBot> {
  const response = await authFetch(`${API_URL}/trading-bots/${botId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return handleResponse<TradingBot>(response);
}

export async function deleteBot(botId: number): Promise<void> {
  const response = await authFetch(`${API_URL}/trading-bots/${botId}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    const error: ApiError = await response.json();
    throw new Error(error.detail || 'Failed to delete bot');
  }
}

export async function fetchBotStats(): Promise<BotStats[]> {
  const response = await authFetch(`${API_URL}/trading-bots/stats`);
  return handleResponse<BotStats[]>(response);
}

export async function fetchAllTrades(): Promise<Trade[]> {
  const response = await authFetch(`${API_URL}/trading-bots/trades/all`);
  return handleResponse<Trade[]>(response);
}

export async function fetchBotTrades(botId: number): Promise<Trade[]> {
  const response = await authFetch(`${API_URL}/trading-bots/${botId}/trades`);
  return handleResponse<Trade[]>(response);
}

export async function emergencySell(botId: number): Promise<{ sold_count: number; price: number }> {
  const response = await authFetch(`${API_URL}/trading-bots/${botId}/emergency-sell`, {
    method: 'POST',
  });
  return handleResponse<{ sold_count: number; price: number }>(response);
}

export interface Kline {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export async function fetchBotKlines(botId: number, interval = "1h", limit = 168): Promise<Kline[]> {
  const response = await authFetch(`${API_URL}/trading-bots/${botId}/klines?interval=${interval}&limit=${limit}`);
  return handleResponse<Kline[]>(response);
}

// ── Simulation types ──────────────────────────────────────────

export interface BacktestMetrics {
  total_pnl: number;
  total_pnl_pct: number;
  num_trades: number;
  num_buys: number;
  num_sells: number;
  win_rate: number;
  max_drawdown: number;
  sharpe_ratio: number;
  final_open_positions: number;
  unrealized_pnl: number;
  min_price: number;
  max_price: number;
  grid_levels: number;
  sell_percentage: number;
  total_amount: number;
}

export interface SimulationResponse {
  symbol: string;
  best_params: BacktestMetrics;
  test_result: BacktestMetrics;
  top_results: BacktestMetrics[];
  train_size: number;
  test_size: number;
  kline_interval: string;
  computed_in_ms: number;
}

export interface ScreeningSymbolResult {
  symbol: string;
  best_pnl_pct: number;
  best_min_price: number;
  best_max_price: number;
  best_grid_levels: number;
  best_sell_percentage: number;
  num_trades: number;
  win_rate: number;
  max_drawdown: number;
  sharpe_ratio: number;
  test_pnl_pct: number;
  test_win_rate: number;
}

export interface ScreeningStatus {
  task_id: string;
  status: "pending" | "running" | "completed" | "failed";
  progress: number;
  total_symbols: number;
  processed_symbols: number;
  results: ScreeningSymbolResult[];
  started_at: string | null;
  completed_at: string | null;
}

// ── Simulation endpoints ──────────────────────────────────────

export async function simulateBot(
  botId: number,
  options?: { interval?: string; limit?: number; total_amount?: number },
): Promise<SimulationResponse> {
  const response = await authFetch(`${API_URL}/simulation/bot/${botId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      interval: options?.interval ?? '1h',
      limit: options?.limit ?? 2000,
      total_amount: options?.total_amount ?? 1000,
    }),
  });
  return handleResponse<SimulationResponse>(response);
}

export async function launchScreening(
  options?: { interval?: string; limit?: number; total_amount?: number },
): Promise<{ task_id: string; message: string }> {
  const response = await authFetch(`${API_URL}/simulation/screening`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      interval: options?.interval ?? '1h',
      limit: options?.limit ?? 2000,
      total_amount: options?.total_amount ?? 1000,
    }),
  });
  return handleResponse<{ task_id: string; message: string }>(response);
}

export async function getScreeningStatus(taskId: string): Promise<ScreeningStatus> {
  const response = await authFetch(`${API_URL}/simulation/screening/${taskId}`);
  return handleResponse<ScreeningStatus>(response);
}
