const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

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

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error: ApiError = await response.json();
    throw new Error(error.detail || 'An error occurred');
  }
  return response.json();
}

export async function register(data: RegisterRequest): Promise<UserResponse> {
  const response = await fetch(`${API_URL}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return handleResponse<UserResponse>(response);
}

export async function login(data: LoginRequest): Promise<TokenResponse> {
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

export async function getMe(accessToken: string): Promise<UserResponse> {
  const response = await fetch(`${API_URL}/auth/me`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  return handleResponse<UserResponse>(response);
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

export async function updateMe(accessToken: string, data: UserUpdateRequest): Promise<UserResponse> {
  const response = await fetch(`${API_URL}/auth/me`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify(data),
  });
  return handleResponse<UserResponse>(response);
}

export async function verifyBinanceKeys(accessToken: string): Promise<{ valid: boolean }> {
  const response = await fetch(`${API_URL}/auth/me/verify-binance`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  return handleResponse<{ valid: boolean }>(response);
}

export async function logout(refreshToken: string): Promise<void> {
  await fetch(`${API_URL}/auth/logout`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
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
  buy_percentage: number;
}

export async function listBots(accessToken: string): Promise<TradingBot[]> {
  const response = await fetch(`${API_URL}/trading-bots`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  return handleResponse<TradingBot[]>(response);
}

export interface TradingBotCreate {
  symbol: string;
  max_price: number;
  min_price: number;
  total_amount: number;
  sell_percentage: number;
  buy_percentage: number;
}

export async function fetchUsdcSymbols(): Promise<string[]> {
  const response = await fetch(`${API_URL}/symbols/usdc`);
  const data = await handleResponse<{ symbols: string[] }>(response);
  return data.symbols;
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

export async function fetchAllTrades(accessToken: string): Promise<Trade[]> {
  const response = await fetch(`${API_URL}/trading-bots/trades/all`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  return handleResponse<Trade[]>(response);
}

export async function fetchBotTrades(accessToken: string, botId: number): Promise<Trade[]> {
  const response = await fetch(`${API_URL}/trading-bots/${botId}/trades`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  return handleResponse<Trade[]>(response);
}

export async function createBot(accessToken: string, data: TradingBotCreate): Promise<TradingBot> {
  const response = await fetch(`${API_URL}/trading-bots`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify(data),
  });
  return handleResponse<TradingBot>(response);
}
