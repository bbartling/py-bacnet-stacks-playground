import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { apiBase } from "@/lib/bas-fetch";

type BasWsEvent = { type?: string; topic?: string; payload?: Record<string, unknown> };

export function useBasWebSocket() {
  const qc = useQueryClient();

  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimer: number | null = null;
    let attempt = 0;
    let stopped = false;

    const invalidateForTopic = (topic?: string) => {
      if (!topic) return;
      if (topic === "system.tick" || topic === "system.metrics.updated") {
        qc.invalidateQueries({ queryKey: ["bas-metrics"] });
        qc.invalidateQueries({ queryKey: ["bas-system-time"] });
      }
      if (topic === "points.updated") {
        qc.invalidateQueries({ queryKey: ["bas-health"] });
        qc.invalidateQueries({ queryKey: ["bas-points"] });
        qc.invalidateQueries({ queryKey: ["bas-devices"] });
        qc.invalidateQueries({ queryKey: ["bas-trend"] });
      }
      if (topic === "alarms.updated") {
        qc.invalidateQueries({ queryKey: ["bas-alarm-events"] });
      }
      if (topic === "schedule.updated") {
        qc.invalidateQueries({ queryKey: ["bas-schedule-effective"] });
      }
      if (topic === "system.tick") {
        qc.invalidateQueries({ queryKey: ["bas-vctl"] });
        qc.invalidateQueries({ queryKey: ["bas-system-containers"] });
        qc.invalidateQueries({ queryKey: ["bas-messaging-status"] });
      }
    };

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
        invalidateForTopic(msg.topic);
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
  }, [qc]);
}

