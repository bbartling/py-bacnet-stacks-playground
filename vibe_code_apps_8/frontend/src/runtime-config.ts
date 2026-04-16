/** Load /app8/config.runtime.js (nginx entrypoint in Docker) before any apiFetch runs. */
export function loadRuntimeGatewayScript(): Promise<void> {
  if (typeof document === "undefined") return Promise.resolve();
  return new Promise((resolve) => {
    const base = (import.meta.env.BASE_URL ?? "/").replace(/\/?$/, "/");
    const src = `${base}config.runtime.js`;
    const s = document.createElement("script");
    s.src = src;
    s.async = false;
    s.onload = () => resolve();
    s.onerror = () => resolve();
    document.head.appendChild(s);
  });
}
