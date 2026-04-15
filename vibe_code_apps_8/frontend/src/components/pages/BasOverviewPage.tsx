import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState, type RefObject } from "react";
import { Link } from "react-router-dom";
import { useTheme } from "@/contexts/theme-context";
import { apiFetch } from "@/lib/bas-fetch";
import { cn } from "@/lib/utils";

type Health = {
  status: string;
  siteName?: string;
  runtimeModel?: { status?: string; note?: string };
  trendPolicy?: { intervalMinutes?: number; retentionDays?: number };
};

type Device = {
  id: string;
  name: string;
  displayName: string;
  kind: string;
  address: string;
  status: string;
  lastSeen: string | null;
  pointCount: number;
  pollingEnabled: boolean;
};

type PointRow = {
  id: string;
  deviceId: string;
  label: string;
  name: string;
  units: string;
  value: unknown;
  lastUpdated: string | null;
  adjustable: boolean;
  alarmState: string;
};

type AlarmEvent = {
  id: string;
  severity: string;
  state: string;
  message: string;
  triggeredAt: string;
  deviceId?: string;
  pointId?: string;
};

type NotificationsCfg = {
  smtp?: {
    enabled?: boolean;
    host?: string;
  };
};

type TrendResp = {
  pointId: string;
  label: string;
  units: string | null;
  items: { ts: string; value: number | string }[];
};

type SetpointWriteOk = {
  status: string;
  pointName?: string;
  requestedValue?: unknown;
  message?: string;
};

function formatValue(value: unknown, units: string): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") {
    const u = units && units !== "bool" ? ` ${units}` : "";
    return `${value.toFixed(1)}${u}`.trim();
  }
  const u = units && units !== "bool" ? ` ${units}` : "";
  return `${String(value)}${u}`.trim();
}

function deviceStatusTone(status: string): "alarm" | "online" | "unknown" {
  const s = status.toLowerCase();
  if (s === "alarm" || s === "offline" || s === "error") return "alarm";
  if (s === "online" || s === "ok") return "online";
  return "unknown";
}

function usePlotlyTrend(
  trend: TrendResp | undefined,
  isDark: boolean,
  plotFullscreen: boolean,
  inlineRef: RefObject<HTMLDivElement | null>,
  fullRef: RefObject<HTMLDivElement | null>,
) {
  useEffect(() => {
    let cancelled = false;
    async function draw() {
      const Plotly = (await import("plotly.js-dist-min")).default as {
        react: (el: HTMLDivElement, data: unknown[], layout: unknown, config: unknown) => void;
      };
      if (cancelled) return;
      const items = trend?.items ?? [];
      const pairs = items
        .map((i) => ({
          x: i.ts,
          y: typeof i.value === "number" ? i.value : Number(i.value),
        }))
        .filter((p) => Number.isFinite(p.y));
      const x = pairs.map((p) => p.x);
      const y = pairs.map((p) => p.y);
      const trace = [
        {
          x,
          y,
          type: "scatter",
          mode: "lines+markers",
          line: { color: isDark ? "#58a6ff" : "#0f62fe", width: 3 },
          marker: { size: 6 },
        },
      ];
      const textMuted = isDark ? "#94a3b8" : "#64748b";
      const grid = isDark ? "rgba(120,140,170,0.15)" : "rgba(100,116,139,0.2)";
      const layout = {
        margin: { l: 48, r: 16, t: 16, b: 42 },
        paper_bgcolor: "transparent",
        plot_bgcolor: "transparent",
        font: { color: textMuted },
        xaxis: { title: "Time", gridcolor: grid },
        yaxis: { title: trend?.units || "value", gridcolor: grid },
      };
      const config = {
        responsive: true,
        displaylogo: false,
        toImageButtonOptions: {
          format: "png",
          filename: `${trend?.pointId ?? "trend"}-trend`,
          height: 500,
          width: 900,
          scale: 1,
        },
      };
      if (inlineRef.current) Plotly.react(inlineRef.current, trace, layout, config);
      if (plotFullscreen && fullRef.current) Plotly.react(fullRef.current, trace, layout, config);
    }
    void draw();
    return () => {
      cancelled = true;
    };
  }, [trend, isDark, plotFullscreen, inlineRef, fullRef]);
}

export function BasOverviewPage() {
  const qc = useQueryClient();
  const { theme } = useTheme();
  const isDark =
    theme === "dark" ||
    (theme === "system" && typeof document !== "undefined" && document.documentElement.classList.contains("dark"));

  const [selectedDeviceId, setSelectedDeviceId] = useState("");
  const [selectedPointId, setSelectedPointId] = useState("");
  const [plotFullscreen, setPlotFullscreen] = useState(false);
  const [writeMessage, setWriteMessage] = useState("");
  const [dockFocus, setDockFocus] = useState(false);

  const [dockPointId, setDockPointId] = useState("");
  const [dockValue, setDockValue] = useState("");

  const poll = dockFocus ? false : 30_000;

  const health = useQuery({
    queryKey: ["bas-health"],
    queryFn: () => apiFetch<Health>("api/health"),
    refetchInterval: poll,
  });

  const devices = useQuery({
    queryKey: ["bas-devices"],
    queryFn: () => apiFetch<{ items: Device[] }>("api/devices"),
    staleTime: 15_000,
    refetchInterval: poll,
  });

  const points = useQuery({
    queryKey: ["bas-points"],
    queryFn: () => apiFetch<{ items: PointRow[] }>("api/points"),
    staleTime: 15_000,
    refetchInterval: poll,
  });

  const alarms = useQuery({
    queryKey: ["bas-alarm-events"],
    queryFn: () => apiFetch<{ items: AlarmEvent[] }>("api/alarms/events"),
    staleTime: 15_000,
    refetchInterval: poll,
  });

  const notifications = useQuery({
    queryKey: ["bas-notifications-config"],
    queryFn: () => apiFetch<NotificationsCfg>("api/notifications/config"),
    staleTime: 60_000,
  });

  useEffect(() => {
    const list = devices.data?.items ?? [];
    if (!list.length) return;
    if (!selectedDeviceId || !list.some((d) => d.id === selectedDeviceId)) {
      setSelectedDeviceId(list[0].id);
    }
  }, [devices.data, selectedDeviceId]);

  const devicePoints = useMemo(
    () => (points.data?.items ?? []).filter((p) => p.deviceId === selectedDeviceId),
    [points.data, selectedDeviceId],
  );

  useEffect(() => {
    if (!devicePoints.length) return;
    if (!selectedPointId || !devicePoints.some((p) => p.id === selectedPointId)) {
      setSelectedPointId(devicePoints[0].id);
    }
  }, [devicePoints, selectedPointId]);

  const trend = useQuery({
    queryKey: ["bas-trend", selectedPointId],
    queryFn: () => apiFetch<TrendResp>(`api/trends?pointId=${encodeURIComponent(selectedPointId)}`),
    enabled: Boolean(selectedPointId),
    refetchInterval: poll,
  });

  const setpoints = useQuery({
    queryKey: ["bas-setpoints", selectedDeviceId],
    queryFn: () =>
      apiFetch<{ items: PointRow[] }>(`api/setpoints?deviceId=${encodeURIComponent(selectedDeviceId)}`),
    enabled: Boolean(selectedDeviceId),
    refetchInterval: poll,
  });

  const selectedDevice = useMemo(
    () => (devices.data?.items ?? []).find((d) => d.id === selectedDeviceId),
    [devices.data, selectedDeviceId],
  );

  const activeAlarmsForDevice = useMemo(() => {
    if (!selectedDevice) return [];
    return (alarms.data?.items ?? []).filter(
      (a) => a.deviceId === selectedDevice.id && a.state === "active",
    );
  }, [alarms.data, selectedDevice]);

  const graphicTiles = useMemo(() => {
    const sorted = [...devicePoints].sort((a, b) => a.label.localeCompare(b.label));
    return sorted.slice(0, 4);
  }, [devicePoints]);

  useEffect(() => {
    const items = setpoints.data?.items ?? [];
    if (!items.length) {
      setDockPointId("");
      return;
    }
    if (!dockPointId || !items.some((p) => p.id === dockPointId)) {
      setDockPointId(items[0].id);
    }
  }, [setpoints.data, dockPointId]);

  const write = useMutation({
    mutationFn: (body: { pointId: string; value: number }) =>
      apiFetch<SetpointWriteOk>("api/setpoints/write", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    onSuccess: async (res) => {
      if (res.status === "ok") {
        setWriteMessage(`Write succeeded: ${res.pointName ?? dockPointId} = ${String(res.requestedValue ?? "")}`);
        setDockValue("");
      } else {
        setWriteMessage(`Write failed: ${res.message ?? dockPointId}`);
      }
      await qc.invalidateQueries({ queryKey: ["bas-points"] });
      await qc.invalidateQueries({ queryKey: ["bas-setpoints", selectedDeviceId] });
      await qc.invalidateQueries({ queryKey: ["bas-trend", selectedPointId] });
    },
    onError: (err: Error) => {
      setWriteMessage(`Write failed: ${err.message}`);
    },
  });

  const selectDevice = useCallback((id: string) => {
    setSelectedDeviceId(id);
    setWriteMessage("");
    const nextPts = (points.data?.items ?? []).filter((p) => p.deviceId === id);
    if (nextPts[0]) setSelectedPointId(nextPts[0].id);
  }, [points.data]);

  const selectPoint = useCallback((id: string) => {
    setSelectedPointId(id);
  }, []);

  const inlinePlotRef = useRef<HTMLDivElement>(null);
  const fullPlotRef = useRef<HTMLDivElement>(null);
  usePlotlyTrend(trend.data, isDark, plotFullscreen, inlinePlotRef, fullPlotRef);

  const runtimeLabel = health.data?.runtimeModel?.status ?? health.data?.status ?? "…";
  const smtp = notifications.data?.smtp;

  if (devices.isLoading || points.isLoading || health.isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-48 animate-pulse rounded-md bg-muted" />
        <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
          <div className="h-96 animate-pulse rounded-2xl bg-muted" />
          <div className="h-96 animate-pulse rounded-2xl bg-muted" />
        </div>
      </div>
    );
  }

  if (!devices.data?.items?.length) {
    return (
      <div className="rounded-2xl border border-border/60 bg-card/40 p-10 text-center">
        <h1 className="text-xl font-semibold">No equipment</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Add driver devices in{" "}
          <Link className="text-primary underline-offset-2 hover:underline" to="/driver">
            Driver configs
          </Link>{" "}
          to mirror the App 7 dashboard.
        </p>
      </div>
    );
  }

  if (!selectedDevice) return null;

  const st = deviceStatusTone(selectedDevice.status);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-0 pb-[220px] lg:pb-[200px]">
      <div className="grid min-h-0 flex-1 gap-5 lg:grid-cols-[minmax(0,280px)_1fr]">
        <aside className="flex flex-col gap-4 rounded-2xl border border-border/60 bg-card/40 p-4 lg:min-h-[480px]">
          <div>
            <h2 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Equipment tree</h2>
            <p className="mt-1 text-xs text-muted-foreground">
              Same layout as{" "}
              <span className="font-medium text-foreground">App 7</span> (live patch + trend + setpoint bar).
            </p>
          </div>
          <div className="flex flex-col gap-2.5">
            {(devices.data?.items ?? []).map((d) => {
              const tone = deviceStatusTone(d.status);
              return (
                <button
                  key={d.id}
                  type="button"
                  onClick={() => selectDevice(d.id)}
                  className={cn(
                    "flex w-full items-start justify-between gap-2 rounded-xl border p-3 text-left transition-colors",
                    selectedDeviceId === d.id
                      ? "border-primary bg-primary/10 shadow-[inset_0_0_0_1px_hsl(var(--primary))]"
                      : "border-border/80 bg-muted/30 hover:bg-muted/50",
                    tone === "alarm" && "border-destructive/60",
                  )}
                >
                  <div>
                    <strong className="text-sm font-semibold">{d.displayName || d.name}</strong>
                    <div className="text-xs uppercase text-muted-foreground">{d.kind}</div>
                  </div>
                  <div className="grid justify-items-end gap-1 text-right text-xs">
                    <span
                      className={cn(
                        "font-medium uppercase tracking-wide",
                        tone === "online" && "text-emerald-600",
                        tone === "alarm" && "text-destructive",
                        tone === "unknown" && "text-amber-600",
                      )}
                    >
                      {d.status}
                    </span>
                    <span className="text-muted-foreground">{d.pointCount}</span>
                  </div>
                </button>
              );
            })}
          </div>
          <p className="mt-auto text-xs text-muted-foreground">
            Full point tree:{" "}
            <Link to="/live-points" className="text-primary underline-offset-2 hover:underline">
              Live points
            </Link>
          </p>
        </aside>

        <main className="flex min-w-0 flex-col gap-4">
          <header className="flex flex-wrap items-start justify-between gap-4 border-b border-border/60 pb-4">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight">{selectedDevice.displayName || selectedDevice.name}</h1>
              <p className="mt-1 text-sm text-muted-foreground">
                Device dashboard: live values refresh in place; use the setpoint bar below (pinned) so typing is not
                interrupted.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <div
                className={cn(
                  "rounded-full border px-3 py-1.5 text-sm font-medium",
                  activeAlarmsForDevice.length
                    ? "border-destructive/60 text-destructive"
                    : "border-border text-emerald-600",
                )}
              >
                {activeAlarmsForDevice.length} active alarm(s)
              </div>
              <div className="rounded-full border border-border px-3 py-1.5 text-sm font-medium text-emerald-600">
                {runtimeLabel}
              </div>
            </div>
          </header>

          <section className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
            <div className="rounded-2xl border border-border/60 bg-card/50 p-4 shadow-sm">
              <div className="mb-4 flex flex-wrap items-center justify-between gap-2 text-sm text-muted-foreground">
                <h3 className="text-base font-semibold text-foreground">{selectedDevice.displayName || selectedDevice.name}</h3>
                <span className="font-mono text-xs">{selectedDevice.address}</span>
              </div>
              <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <div className="rounded-xl border border-border/60 bg-muted/30 p-3">
                  <span className="text-xs font-medium uppercase text-muted-foreground">Status</span>
                  <p
                    className={cn(
                      "mt-1 text-lg font-semibold capitalize",
                      st === "online" && "text-emerald-600",
                      st === "alarm" && "text-destructive",
                      st === "unknown" && "text-amber-600",
                    )}
                  >
                    {selectedDevice.status}
                  </p>
                </div>
                <div className="rounded-xl border border-border/60 bg-muted/30 p-3">
                  <span className="text-xs font-medium uppercase text-muted-foreground">Points</span>
                  <p className="mt-1 text-lg font-semibold">{selectedDevice.pointCount}</p>
                </div>
                <div className="rounded-xl border border-border/60 bg-muted/30 p-3">
                  <span className="text-xs font-medium uppercase text-muted-foreground">Polling</span>
                  <p className="mt-1 text-lg font-semibold">{selectedDevice.pollingEnabled ? "enabled" : "disabled"}</p>
                </div>
                <div className="rounded-xl border border-border/60 bg-muted/30 p-3">
                  <span className="text-xs font-medium uppercase text-muted-foreground">Active alarms</span>
                  <p className="mt-1 text-lg font-semibold">{activeAlarmsForDevice.length}</p>
                </div>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                {graphicTiles.map((pt) => {
                  const alarm = pt.alarmState === "alarm";
                  return (
                    <button
                      key={pt.id}
                      type="button"
                      onClick={() => selectPoint(pt.id)}
                      className={cn(
                        "rounded-xl border p-3 text-left transition-colors",
                        selectedPointId === pt.id
                          ? "border-primary bg-primary/10 shadow-[inset_0_0_0_1px_hsl(var(--primary))]"
                          : "border-border/60 bg-muted/20 hover:bg-muted/40",
                        alarm && "border-destructive/50",
                      )}
                    >
                      <span className="text-xs font-medium uppercase text-muted-foreground">{pt.label}</span>
                      <p className="mt-1 text-lg font-semibold">{formatValue(pt.value, pt.units)}</p>
                      <span className="text-xs text-muted-foreground">
                        {pt.adjustable ? "writable setpoint" : "read only"}
                      </span>
                    </button>
                  );
                })}
                {graphicTiles.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No points for this device yet.</p>
                ) : null}
              </div>
            </div>

            <div className="rounded-2xl border border-border/60 bg-card/50 p-4 shadow-sm">
              <div className="mb-3 flex items-center justify-between gap-2">
                <h3 className="text-base font-semibold">Alarm state</h3>
                <span className="text-xs text-muted-foreground">
                  {activeAlarmsForDevice.length ? "attention needed" : "quiet"}
                </span>
              </div>
              <div className="flex max-h-[280px] flex-col gap-2 overflow-y-auto">
                {activeAlarmsForDevice.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No active alarms for this equipment.</p>
                ) : (
                  activeAlarmsForDevice.map((a) => (
                    <div
                      key={a.id}
                      className={cn(
                        "flex items-start justify-between gap-2 rounded-xl border p-3",
                        a.severity === "critical" ? "border-destructive/60 bg-destructive/5" : "border-border/60 bg-muted/20",
                      )}
                    >
                      <div>
                        <strong className="text-sm">{a.message}</strong>
                        <p className="mt-0.5 text-xs text-muted-foreground">{a.state}</p>
                      </div>
                      <div className="grid shrink-0 justify-items-end gap-1 text-right text-xs text-muted-foreground">
                        <span className="font-medium uppercase tracking-wide">{a.severity}</span>
                        <span>{a.triggeredAt}</span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </section>

          <section className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
            <div className="rounded-2xl border border-border/60 bg-card/50 p-4 shadow-sm">
              <div className="mb-3 flex items-center justify-between gap-2">
                <h3 className="text-base font-semibold">Point table</h3>
                <span className="text-xs text-muted-foreground">{devicePoints.length} points</span>
              </div>
              <div className="max-h-[min(52vh,520px)] overflow-auto rounded-lg border border-border/50">
                <table className="w-full border-collapse text-sm">
                  <thead>
                    <tr className="border-b border-border/60 bg-muted/40 text-left text-xs text-muted-foreground">
                      <th className="sticky top-0 z-10 bg-muted/90 px-3 py-2 font-medium backdrop-blur">Point</th>
                      <th className="sticky top-0 z-10 bg-muted/90 px-3 py-2 font-medium backdrop-blur">Value</th>
                      <th className="sticky top-0 z-10 bg-muted/90 px-3 py-2 font-medium backdrop-blur">Last updated</th>
                      <th className="sticky top-0 z-10 bg-muted/90 px-3 py-2 font-medium backdrop-blur">Adj.</th>
                      <th className="sticky top-0 z-10 bg-muted/90 px-3 py-2 font-medium backdrop-blur">Alarm</th>
                    </tr>
                  </thead>
                  <tbody>
                    {devicePoints.map((p) => {
                      const rowAlarm = p.alarmState === "alarm";
                      return (
                        <tr
                          key={p.id}
                          role="button"
                          tabIndex={0}
                          onClick={() => selectPoint(p.id)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" || e.key === " ") {
                              e.preventDefault();
                              selectPoint(p.id);
                            }
                          }}
                          className={cn(
                            "cursor-pointer border-b border-border/40 last:border-0",
                            rowAlarm && "text-destructive",
                            selectedPointId === p.id && "bg-primary/10",
                          )}
                        >
                          <td className="px-3 py-2">{p.label}</td>
                          <td className="px-3 py-2 font-mono">{formatValue(p.value, p.units)}</td>
                          <td className="px-3 py-2 text-xs text-muted-foreground">{p.lastUpdated ?? "—"}</td>
                          <td className="px-3 py-2 text-xs">{p.adjustable ? "yes" : "no"}</td>
                          <td className="px-3 py-2 text-xs">{p.alarmState}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="rounded-2xl border border-border/60 bg-card/50 p-4 shadow-sm">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-base font-semibold">Trend</h3>
                <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <span className="max-w-[200px] truncate font-medium text-foreground">{trend.data?.label ?? "…"}</span>
                  <button
                    type="button"
                    className="rounded-lg border border-border bg-muted/50 px-2 py-1 text-xs font-medium text-foreground hover:bg-muted"
                    onClick={() => setPlotFullscreen(true)}
                  >
                    Full screen Plotly
                  </button>
                </div>
              </div>
              <div
                ref={inlinePlotRef}
                className="min-h-[360px] w-full rounded-xl border border-border/60 bg-muted/20"
              />
              <p className="mt-2 text-xs text-muted-foreground">
                Samples: {trend.data?.items?.length ?? 0}
                {health.data?.trendPolicy
                  ? ` · policy ~${health.data.trendPolicy.intervalMinutes ?? "?"} min / ${health.data.trendPolicy.retentionDays ?? "?"} d`
                  : null}
              </p>
            </div>
          </section>

          <section className="rounded-2xl border border-border/60 bg-card/50 p-4 shadow-sm">
            <div className="mb-3 flex items-center justify-between gap-2">
              <h3 className="text-base font-semibold">Operator notes</h3>
              <span className="text-xs text-muted-foreground">bench mode</span>
            </div>
            <div className="grid gap-2 text-sm">
              <div className="flex justify-between gap-2 rounded-lg border border-border/60 bg-muted/20 px-3 py-2">
                <span className="text-muted-foreground">Alarm setup</span>
                <span>Alarms page / OpenClaw chat</span>
              </div>
              <div className="flex justify-between gap-2 rounded-lg border border-border/60 bg-muted/20 px-3 py-2">
                <span className="text-muted-foreground">Trend</span>
                <span>this overview (Plotly)</span>
              </div>
              <div className="flex justify-between gap-2 rounded-lg border border-border/60 bg-muted/20 px-3 py-2">
                <span className="text-muted-foreground">Email notifications</span>
                <span>{smtp?.enabled ? "enabled" : "planned / placeholder"}</span>
              </div>
              <div className="flex justify-between gap-2 rounded-lg border border-border/60 bg-muted/20 px-3 py-2">
                <span className="text-muted-foreground">SMTP host</span>
                <span className="truncate font-mono text-xs">{smtp?.host ?? "—"}</span>
              </div>
            </div>
            <p className="mt-3 text-xs text-muted-foreground">
              Configure SMTP and rules on the{" "}
              <Link to="/alarms" className="text-primary underline-offset-2 hover:underline">
                Alarms
              </Link>{" "}
              page.
            </p>
          </section>
        </main>
      </div>

      {plotFullscreen ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/55 p-4"
          role="presentation"
          onClick={() => setPlotFullscreen(false)}
        >
          <div
            className="max-h-[90vh] w-full max-w-[900px] overflow-auto rounded-2xl border border-border bg-card p-4 shadow-xl"
            role="dialog"
            aria-modal="true"
            aria-label="Full screen trend"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-3 flex items-center justify-between gap-2">
              <h3 className="text-base font-semibold">Full screen trend</h3>
              <button
                type="button"
                className="rounded-lg border border-border px-3 py-1 text-sm hover:bg-muted"
                onClick={() => setPlotFullscreen(false)}
              >
                Close
              </button>
            </div>
            <div ref={fullPlotRef} className="min-h-[50vh] w-full rounded-xl border border-border/60 bg-muted/20" />
          </div>
        </div>
      ) : null}

      <aside
        className="fixed bottom-0 left-0 right-0 z-40 border-t border-border/60 bg-gradient-to-t from-card to-muted/30 px-4 py-4 shadow-[0_-8px_24px_rgba(0,0,0,0.12)] dark:shadow-[0_-8px_24px_rgba(0,0,0,0.35)] lg:left-60"
        aria-label="Write BACnet setpoint"
      >
        <div className="mx-auto max-w-3xl">
          <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
            <div>
              <strong className="text-sm">Setpoint write</strong>
              <div className="text-xs text-muted-foreground">Platform driver · priority write</div>
            </div>
            <span className="text-xs text-muted-foreground">{selectedDevice.displayName || selectedDevice.name}</span>
          </div>
          <div className="grid gap-3 sm:grid-cols-[auto_1fr_auto] sm:items-end">
            <label className="grid gap-1 text-xs text-muted-foreground sm:col-span-1">
              Point
              <select
                id="setpoint-target-select"
                className="w-full max-w-md rounded-lg border border-border bg-background px-3 py-2 text-sm"
                value={dockPointId}
                onFocus={() => setDockFocus(true)}
                onBlur={() => setDockFocus(false)}
                onChange={(e) => setDockPointId(e.target.value)}
              >
                {(setpoints.data?.items ?? []).length ? (
                  (setpoints.data?.items ?? []).map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.label} ({p.name})
                    </option>
                  ))
                ) : (
                  <option value="">(no writable points)</option>
                )}
              </select>
            </label>
            <label className="grid gap-1 text-xs text-muted-foreground">
              New value
              <input
                id="setpoint-value-input"
                type="number"
                step="any"
                inputMode="decimal"
                autoComplete="off"
                placeholder="e.g. 72"
                className="max-w-[200px] rounded-lg border border-border bg-background px-3 py-2 text-sm"
                value={dockValue}
                onFocus={() => setDockFocus(true)}
                onBlur={() => setDockFocus(false)}
                onChange={(e) => setDockValue(e.target.value)}
              />
            </label>
            <button
              type="button"
              className="rounded-lg border border-primary bg-primary/15 px-4 py-2 text-sm font-medium text-foreground hover:bg-primary/25 disabled:opacity-50"
              disabled={write.isPending || !dockPointId}
              onClick={() => {
                const n = Number(dockValue);
                if (dockValue === "" || Number.isNaN(n)) {
                  setWriteMessage("Enter a valid number.");
                  return;
                }
                setWriteMessage("");
                write.mutate({ pointId: dockPointId, value: n });
              }}
            >
              Write to BACnet
            </button>
          </div>
          <div className="mt-2 min-h-[1.25em] text-sm text-muted-foreground" role="status">
            {write.isPending ? "Writing…" : writeMessage}
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            This bar stays fixed while the overview above scrolls, similar to the App 7 dock outside the main scroll
            region.
          </p>
        </div>
      </aside>
    </div>
  );
}
