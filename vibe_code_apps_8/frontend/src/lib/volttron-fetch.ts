/**
 * Fetch JSON same-origin under the SPA base (e.g. `/app8/`) — Docker + Caddy + easy-aso API.
 */
export function volttronBase(): string {
  const b = (import.meta.env.BASE_URL ?? "/").replace(/\/?$/, "/");
  return b === "//" ? "/" : b;
}

export function volttronUrl(path: string): string {
  const p = path.startsWith("/") ? path.slice(1) : path;
  return `${volttronBase()}${p}`;
}

export async function vtFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const url = volttronUrl(path);
  const res = await fetch(url, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.headers as Record<string, string>),
    },
  });
  if (!res.ok) {
    const t = await res.text().catch(() => "");
    throw new Error(`${res.status} ${t || res.statusText}`.trim());
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
