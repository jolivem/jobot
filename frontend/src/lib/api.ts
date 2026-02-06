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
