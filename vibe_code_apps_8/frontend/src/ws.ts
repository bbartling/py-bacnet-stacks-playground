import { apiBase } from "./api";
import { emitTopic } from "./topics";

type BasWsEvent = { type?: string; topic?: string; payload?: Record<string, unknown> };

export function connectBasWebSocket(): () => void {
  let ws: WebSocket | null = null;
  let reconnectTimer: number | null = null;
  let attempt = 0;
  let stopped = false;

  const connect = () => {
    const base = apiBase().replace(/\/$/, "");
    const wsPath = `${base}/api/ws/events`.replace(/\/{2,}/g, "/");
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${window.location.host}${wsPath}`;
    ws = new WebSocket(url);

    ws.onopen = () => {
      attempt = 0;
    };
    ws.onmessage = (evt) => {
      let msg: BasWsEvent | null = null;
      try {
        msg = JSON.parse(evt.data) as BasWsEvent;
      } catch {
        return;
      }
      if (msg?.type !== "event") return;
      if (msg.topic) emitTopic(msg.topic);
    };
    ws.onclose = () => {
      if (stopped) return;
      const delay = Math.min(30_000, 1000 * 2 ** Math.min(attempt, 5));
      attempt += 1;
      reconnectTimer = window.setTimeout(connect, delay);
    };
  };

  connect();
  return () => {
    stopped = true;
    if (reconnectTimer != null) window.clearTimeout(reconnectTimer);
    try {
      ws?.close();
    } catch {
      // ignore
    }
  };
}
