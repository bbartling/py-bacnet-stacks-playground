/** Fetch JSON same-origin under the SPA base (e.g. `/app8/`) — Docker + Caddy + easy-aso API. */
export function apiBase(): string {
  const b = (import.meta.env.BASE_URL ?? "/").replace(/\/?$/, "/");
  return b === "//" ? "/" : b;
}

export function apiUrl(path: string): string {
  const p = path.startsWith("/") ? path.slice(1) : path;
  return `${apiBase()}${p}`;
}

/** Gateway bearer from nginx-generated /app8/config.runtime.js (Docker); not used in dev unless file is present. */
function gatewayBearerFromRuntime(): string | undefined {
  if (typeof window === "undefined") return undefined;
  const w = (window as unknown as { __BAS_LITE__?: { gatewayTokenB64?: string } }).__BAS_LITE__;
  const b64 = w?.gatewayTokenB64?.trim();
  if (!b64) return undefined;
  try {
    const raw = atob(b64);
    if (!raw) return undefined;
    return `Bearer ${raw}`;
  } catch {
    return undefined;
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const url = apiUrl(path);
  const gw = gatewayBearerFromRuntime();
  const res = await fetch(url, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.headers as Record<string, string>),
      ...(gw ? { "X-Bas-Lite-Gateway-Token": gw } : {}),
    },
  });
  if (!res.ok) {
    const t = await res.text().catch(() => "");
    throw new Error(`${res.status} ${t || res.statusText}`.trim());
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
