import { logger } from "./logger";

const TOKEN_KEY = "vibe12_token";

export class ApiError extends Error {
  status: number;
  path: string;
  body: string;
  constructor(status: number, path: string, body: string) {
    super(`API ${status} ${path}`);
    this.status = status;
    this.path = path;
    this.body = body;
  }
}

function storage(): Storage | null {
  return typeof window !== "undefined" ? window.sessionStorage : null;
}

export function getToken(): string | null {
  return storage()?.getItem(TOKEN_KEY) ?? null;
}

export function setToken(token: string | null) {
  const s = storage();
  if (!s) return;
  if (token) s.setItem(TOKEN_KEY, token);
  else s.removeItem(TOKEN_KEY);
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const reqId = crypto.randomUUID().slice(0, 8);
  const method = init?.method ?? "GET";
  const t0 = performance.now();
  const headers = new Headers(init?.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (!headers.has("Content-Type") && init?.body) {
    headers.set("Content-Type", "application/json");
  }
  headers.set("X-Request-Id", reqId);

  logger.info("api", `${method} ${path}`, { reqId });

  let res: Response;
  try {
    res = await fetch(path, { ...init, headers });
  } catch (err) {
    const detail = err instanceof Error ? err.message : String(err);
    logger.error("api", `network ${path}`, { reqId, detail });
    throw new Error(`Network error on ${path}: ${detail}`);
  }

  const ms = Math.round(performance.now() - t0);
  const raw = await res.text();

  if (!res.ok) {
    logger.error("api", `${res.status} ${path} (${ms}ms)`, {
      reqId,
      body: raw.slice(0, 400),
    });
    throw new ApiError(res.status, path, raw);
  }

  logger.info("api", `${res.status} ${path} (${ms}ms)`, { reqId });
  if (!raw) return {} as T;
  try {
    return JSON.parse(raw) as T;
  } catch {
    throw new Error(`Non-JSON response from ${path}`);
  }
}

export async function apiFetchText(path: string, init?: RequestInit): Promise<string> {
  const token = getToken();
  const headers = new Headers(init?.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(path, { ...init, headers });
  const text = await res.text();
  if (!res.ok) throw new ApiError(res.status, path, text);
  return text;
}

export type LoginResponse = {
  ok: boolean;
  token: string;
  username: string;
  auth_required: boolean;
};

export type MeResponse = {
  ok: boolean;
  username: string;
  auth_required: boolean;
};

export async function login(username: string, password: string): Promise<LoginResponse> {
  const data = await apiFetch<LoginResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  if (data.token) setToken(data.token);
  return data;
}

export async function fetchMe(): Promise<MeResponse> {
  return apiFetch<MeResponse>("/api/auth/me");
}
