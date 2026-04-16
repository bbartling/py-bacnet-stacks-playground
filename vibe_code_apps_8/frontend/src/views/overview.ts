import { html, render } from "lit-html";
import { apiFetch } from "../api";
import { getGlobalPollPaused, setGlobalPollDockFocus } from "../shell";
import { subscribeTopics } from "../topics";
import { cn } from "../util";
import type { MountFn } from "./types";

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

function formatValue(value: unknown, units: string): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return String(value);
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

export const mountOverview: MountFn = (outlet, ctx) => {
  let devices: Device[] = [];
  let points: PointRow[] = [];
  let alarms: AlarmEvent[] = [];
  let health: Health | null = null;
  let notifications: NotificationsCfg | null = null;
  let trend: TrendResp | null = null;
  let setpoints: PointRow[] = [];
  let selectedDeviceId = "";
  let selectedPointId = "";
  let plotFullscreen = false;
  let writeMessage = "";
  let dockPointId = "";
  let dockValue = "";
  let writing = false;
  let loading = true;
  let cancelled = false;

  const dockHandler = (e: Event) => {
    const t = e.target as HTMLElement | null;
    if (!t) return;
    const dock = t.closest("[data-bas-dock]");
    setGlobalPollDockFocus(Boolean(dock));
  };

  const paint = () => {
    const isDark = document.documentElement.classList.contains("dark");

    if (loading) {
      render(
        html`
          <div class="space-y-4">
            <div class="h-8 w-48 animate-pulse rounded-md bg-muted"></div>
            <div class="grid gap-4 lg:grid-cols-[280px_1fr]">
              <div class="h-96 animate-pulse rounded-2xl bg-muted"></div>
              <div class="h-96 animate-pulse rounded-2xl bg-muted"></div>
            </div>
          </div>
        `,
        outlet,
      );
      return;
    }

    if (!devices.length) {
      render(
        html`
          <div class="rounded-2xl border border-border/60 bg-card/40 p-10 text-center">
            <h1 class="text-xl font-semibold">No equipment</h1>
            <p class="mt-2 text-sm text-muted-foreground">
              Add driver devices in
              <button type="button" class="text-primary underline" @click=${() => ctx.navigate("driver")}>
                Driver configs
              </button>
              to mirror the App 7 dashboard.
            </p>
          </div>
        `,
        outlet,
      );
      return;
    }

    const selectedDevice = devices.find((d) => d.id === selectedDeviceId) ?? devices[0];
    const devicePoints = points.filter((p) => p.deviceId === selectedDevice.id);
    const activeAlarmsForDevice = alarms.filter(
      (a) => a.deviceId === selectedDevice.id && a.state === "active",
    );
    const graphicTiles = [...devicePoints].sort((a, b) => a.label.localeCompare(b.label)).slice(0, 4);
    const st = deviceStatusTone(selectedDevice.status);
    const runtimeLabel = health?.runtimeModel?.status ?? health?.status ?? "…";
    const smtp = notifications?.smtp;

    render(
      html`
        <div class="flex min-h-0 flex-1 flex-col gap-0 pb-[220px] lg:pb-[200px]">
          <div class="grid min-h-0 flex-1 gap-5 lg:grid-cols-[minmax(0,280px)_1fr]">
            <aside class="flex flex-col gap-4 rounded-2xl border border-border/60 bg-card/40 p-4 lg:min-h-[480px]">
              <div>
                <h2 class="text-xs font-medium uppercase tracking-wide text-muted-foreground">Equipment tree</h2>
                <p class="mt-1 text-xs text-muted-foreground">
                  Same layout as <span class="font-medium text-foreground">App 7</span> (live patch + trend + setpoint
                  bar).
                </p>
              </div>
              <div class="flex flex-col gap-2.5">
                ${devices.map((d) => {
                  const tone = deviceStatusTone(d.status);
                  return html`
                    <button
                      type="button"
                      class=${cn(
                        "flex w-full items-start justify-between gap-2 rounded-xl border p-3 text-left transition-colors",
                        selectedDevice.id === d.id
                          ? "border-primary bg-primary/10 shadow-[inset_0_0_0_1px_hsl(var(--primary))]"
                          : "border-border/80 bg-muted/30 hover:bg-muted/50",
                        tone === "alarm" && "border-destructive/60",
                      )}
                      @click=${() => void selectDevice(d.id)}
                    >
                      <div>
                        <strong class="text-sm font-semibold">${d.displayName || d.name}</strong>
                        <div class="text-xs uppercase text-muted-foreground">${d.kind}</div>
                      </div>
                      <div class="grid justify-items-end gap-1 text-right text-xs">
                        <span
                          class=${cn(
                            "font-medium uppercase tracking-wide",
                            tone === "online" && "text-emerald-600",
                            tone === "alarm" && "text-destructive",
                            tone === "unknown" && "text-amber-600",
                          )}
                        >
                          ${d.status}
                        </span>
                        <span class="text-muted-foreground">${d.pointCount}</span>
                      </div>
                    </button>
                  `;
                })}
              </div>
              <p class="mt-auto text-xs text-muted-foreground">
                Full point tree:
                <button type="button" class="text-primary underline" @click=${() => ctx.navigate("live-points")}>
                  Live points
                </button>
              </p>
            </aside>

            <main class="flex min-w-0 flex-col gap-4">
              <header class="flex flex-wrap items-start justify-between gap-4 border-b border-border/60 pb-4">
                <div>
                  <h1 class="text-2xl font-semibold tracking-tight">
                    ${selectedDevice.displayName || selectedDevice.name}
                  </h1>
                  <p class="mt-1 text-sm text-muted-foreground">
                    Device dashboard: live values refresh in place; use the setpoint bar below (pinned) so typing is not
                    interrupted.
                  </p>
                </div>
                <div class="flex flex-wrap gap-2">
                  <div
                    class=${cn(
                      "rounded-full border px-3 py-1.5 text-sm font-medium",
                      activeAlarmsForDevice.length
                        ? "border-destructive/60 text-destructive"
                        : "border-border text-emerald-600",
                    )}
                  >
                    ${activeAlarmsForDevice.length} active alarm(s)
                  </div>
                  <div class="rounded-full border border-border px-3 py-1.5 text-sm font-medium text-emerald-600">
                    ${runtimeLabel}
                  </div>
                </div>
              </header>

              <section class="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
                <div class="rounded-2xl border border-border/60 bg-card/50 p-4 shadow-sm">
                  <div class="mb-4 flex flex-wrap items-center justify-between gap-2 text-sm text-muted-foreground">
                    <h3 class="text-base font-semibold text-foreground">
                      ${selectedDevice.displayName || selectedDevice.name}
                    </h3>
                    <span class="font-mono text-xs">${selectedDevice.address}</span>
                  </div>
                  <div class="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    <div class="rounded-xl border border-border/60 bg-muted/30 p-3">
                      <span class="text-xs font-medium uppercase text-muted-foreground">Status</span>
                      <p
                        class=${cn(
                          "mt-1 text-lg font-semibold capitalize",
                          st === "online" && "text-emerald-600",
                          st === "alarm" && "text-destructive",
                          st === "unknown" && "text-amber-600",
                        )}
                      >
                        ${selectedDevice.status}
                      </p>
                    </div>
                    <div class="rounded-xl border border-border/60 bg-muted/30 p-3">
                      <span class="text-xs font-medium uppercase text-muted-foreground">Points</span>
                      <p class="mt-1 text-lg font-semibold">${selectedDevice.pointCount}</p>
                    </div>
                    <div class="rounded-xl border border-border/60 bg-muted/30 p-3">
                      <span class="text-xs font-medium uppercase text-muted-foreground">Polling</span>
                      <p class="mt-1 text-lg font-semibold">${selectedDevice.pollingEnabled ? "enabled" : "disabled"}</p>
                    </div>
                    <div class="rounded-xl border border-border/60 bg-muted/30 p-3">
                      <span class="text-xs font-medium uppercase text-muted-foreground">Active alarms</span>
                      <p class="mt-1 text-lg font-semibold">${activeAlarmsForDevice.length}</p>
                    </div>
                  </div>
                  <div class="grid gap-3 sm:grid-cols-2">
                    ${graphicTiles.map((pt) => {
                      const alarm = pt.alarmState === "alarm";
                      return html`
                        <button
                          type="button"
                          class=${cn(
                            "rounded-xl border p-3 text-left transition-colors",
                            selectedPointId === pt.id
                              ? "border-primary bg-primary/10 shadow-[inset_0_0_0_1px_hsl(var(--primary))]"
                              : "border-border/60 bg-muted/20 hover:bg-muted/40",
                            alarm && "border-destructive/50",
                          )}
                          @click=${() => {
                            selectedPointId = pt.id;
                            void loadTrend();
                            paint();
                          }}
                        >
                          <span class="text-xs font-medium uppercase text-muted-foreground">${pt.label}</span>
                          <p class="mt-1 text-lg font-semibold">${formatValue(pt.value, pt.units)}</p>
                          <span class="text-xs text-muted-foreground">
                            ${pt.adjustable ? "writable setpoint" : "read only"}
                          </span>
                        </button>
                      `;
                    })}
                    ${graphicTiles.length === 0
                      ? html`<p class="text-sm text-muted-foreground">No points for this device yet.</p>`
                      : null}
                  </div>
                </div>

                <div class="rounded-2xl border border-border/60 bg-card/50 p-4 shadow-sm">
                  <div class="mb-3 flex items-center justify-between gap-2">
                    <h3 class="text-base font-semibold">Alarm state</h3>
                    <span class="text-xs text-muted-foreground">
                      ${activeAlarmsForDevice.length ? "attention needed" : "quiet"}
                    </span>
                  </div>
                  <div class="flex max-h-[280px] flex-col gap-2 overflow-y-auto">
                    ${activeAlarmsForDevice.length === 0
                      ? html`<p class="text-sm text-muted-foreground">No active alarms for this equipment.</p>`
                      : activeAlarmsForDevice.map(
                          (a) => html`
                            <div
                              class=${cn(
                                "flex items-start justify-between gap-2 rounded-xl border p-3",
                                a.severity === "critical"
                                  ? "border-destructive/60 bg-destructive/5"
                                  : "border-border/60 bg-muted/20",
                              )}
                            >
                              <div>
                                <strong class="text-sm">${a.message}</strong>
                                <p class="mt-0.5 text-xs text-muted-foreground">${a.state}</p>
                              </div>
                              <div class="grid shrink-0 justify-items-end gap-1 text-right text-xs text-muted-foreground">
                                <span class="font-medium uppercase tracking-wide">${a.severity}</span>
                                <span>${a.triggeredAt}</span>
                              </div>
                            </div>
                          `,
                        )}
                  </div>
                </div>
              </section>

              <section class="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
                <div class="rounded-2xl border border-border/60 bg-card/50 p-4 shadow-sm">
                  <div class="mb-3 flex items-center justify-between gap-2">
                    <h3 class="text-base font-semibold">Point table</h3>
                    <span class="text-xs text-muted-foreground">${devicePoints.length} points</span>
                  </div>
                  <div class="max-h-[min(52vh,520px)] overflow-auto rounded-lg border border-border/50">
                    <table class="w-full border-collapse text-sm">
                      <thead>
                        <tr class="border-b border-border/60 bg-muted/40 text-left text-xs text-muted-foreground">
                          <th class="sticky top-0 z-10 bg-muted/90 px-3 py-2 font-medium backdrop-blur">Point</th>
                          <th class="sticky top-0 z-10 bg-muted/90 px-3 py-2 font-medium backdrop-blur">Value</th>
                          <th class="sticky top-0 z-10 bg-muted/90 px-3 py-2 font-medium backdrop-blur">Last updated</th>
                          <th class="sticky top-0 z-10 bg-muted/90 px-3 py-2 font-medium backdrop-blur">Adj.</th>
                          <th class="sticky top-0 z-10 bg-muted/90 px-3 py-2 font-medium backdrop-blur">Alarm</th>
                        </tr>
                      </thead>
                      <tbody>
                        ${devicePoints.map((p) => {
                          const rowAlarm = p.alarmState === "alarm";
                          return html`
                            <tr
                              class=${cn(
                                "cursor-pointer border-b border-border/40 last:border-0",
                                rowAlarm && "text-destructive",
                                selectedPointId === p.id && "bg-primary/10",
                              )}
                              @click=${() => {
                                selectedPointId = p.id;
                                void loadTrend();
                                paint();
                              }}
                            >
                              <td class="px-3 py-2">${p.label}</td>
                              <td class="px-3 py-2 font-mono">${formatValue(p.value, p.units)}</td>
                              <td class="px-3 py-2 text-xs text-muted-foreground">${p.lastUpdated ?? "—"}</td>
                              <td class="px-3 py-2 text-xs">${p.adjustable ? "yes" : "no"}</td>
                              <td class="px-3 py-2 text-xs">${p.alarmState}</td>
                            </tr>
                          `;
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>

                <div class="rounded-2xl border border-border/60 bg-card/50 p-4 shadow-sm">
                  <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
                    <h3 class="text-base font-semibold">Trend</h3>
                    <div class="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                      <span class="max-w-[200px] truncate font-medium text-foreground">${trend?.label ?? "…"}</span>
                      <button
                        type="button"
                        class="rounded-lg border border-border bg-muted/50 px-2 py-1 text-xs font-medium text-foreground hover:bg-muted"
                        @click=${() => {
                          plotFullscreen = true;
                          paint();
                        }}
                      >
                        Full screen Plotly
                      </button>
                    </div>
                  </div>
                  <div
                    id="bas-inline-plot"
                    class="min-h-[360px] w-full rounded-xl border border-border/60 bg-muted/20"
                  ></div>
                  <p class="mt-2 text-xs text-muted-foreground">
                    Samples: ${trend?.items?.length ?? 0}
                    ${health?.trendPolicy
                      ? ` · policy ~${health.trendPolicy.intervalMinutes ?? "?"} min / ${health.trendPolicy.retentionDays ?? "?"} d`
                      : null}
                  </p>
                </div>
              </section>

              <section class="rounded-2xl border border-border/60 bg-card/50 p-4 shadow-sm">
                <div class="mb-3 flex items-center justify-between gap-2">
                  <h3 class="text-base font-semibold">Operator notes</h3>
                  <span class="text-xs text-muted-foreground">bench mode</span>
                </div>
                <div class="grid gap-2 text-sm">
                  <div class="flex justify-between gap-2 rounded-lg border border-border/60 bg-muted/20 px-3 py-2">
                    <span class="text-muted-foreground">Alarm setup</span>
                    <span>Alarms page / OpenClaw chat</span>
                  </div>
                  <div class="flex justify-between gap-2 rounded-lg border border-border/60 bg-muted/20 px-3 py-2">
                    <span class="text-muted-foreground">Trend</span>
                    <span>this overview (Plotly)</span>
                  </div>
                  <div class="flex justify-between gap-2 rounded-lg border border-border/60 bg-muted/20 px-3 py-2">
                    <span class="text-muted-foreground">Email notifications</span>
                    <span>${smtp?.enabled ? "enabled" : "planned / placeholder"}</span>
                  </div>
                  <div class="flex justify-between gap-2 rounded-lg border border-border/60 bg-muted/20 px-3 py-2">
                    <span class="text-muted-foreground">SMTP host</span>
                    <span class="truncate font-mono text-xs">${smtp?.host ?? "—"}</span>
                  </div>
                </div>
                <p class="mt-3 text-xs text-muted-foreground">
                  Configure SMTP and rules on the
                  <button type="button" class="text-primary underline" @click=${() => ctx.navigate("alarms")}>
                    Alarms
                  </button>
                  page.
                </p>
              </section>
            </main>
          </div>

          ${plotFullscreen
            ? html`
                <div
                  class="fixed inset-0 z-50 flex items-center justify-center bg-black/55 p-4"
                  role="presentation"
                  @click=${() => {
                    plotFullscreen = false;
                    paint();
                  }}
                >
                  <div
                    class="max-h-[90vh] w-full max-w-[900px] overflow-auto rounded-2xl border border-border bg-card p-4 shadow-xl"
                    role="dialog"
                    aria-modal="true"
                    aria-label="Full screen trend"
                    @click=${(e: Event) => e.stopPropagation()}
                  >
                    <div class="mb-3 flex items-center justify-between gap-2">
                      <h3 class="text-base font-semibold">Full screen trend</h3>
                      <button
                        type="button"
                        class="rounded-lg border border-border px-3 py-1 text-sm hover:bg-muted"
                        @click=${() => {
                          plotFullscreen = false;
                          paint();
                        }}
                      >
                        Close
                      </button>
                    </div>
                    <div
                      id="bas-full-plot"
                      class="min-h-[50vh] w-full rounded-xl border border-border/60 bg-muted/20"
                    ></div>
                  </div>
                </div>
              `
            : null}

          <aside
            data-bas-dock
            class="fixed bottom-0 left-0 right-0 z-40 border-t border-border/60 bg-gradient-to-t from-card to-muted/30 px-4 py-4 shadow-[0_-8px_24px_rgba(0,0,0,0.12)] dark:shadow-[0_-8px_24px_rgba(0,0,0,0.35)] lg:left-60"
            aria-label="Write BACnet setpoint"
          >
            <div class="mx-auto max-w-3xl">
              <div class="mb-3 flex flex-wrap items-start justify-between gap-2">
                <div>
                  <strong class="text-sm">Setpoint write</strong>
                  <div class="text-xs text-muted-foreground">Platform driver · priority write</div>
                </div>
                <span class="text-xs text-muted-foreground">${selectedDevice.displayName || selectedDevice.name}</span>
              </div>
              <div class="grid gap-3 sm:grid-cols-[auto_1fr_auto] sm:items-end">
                <label class="grid gap-1 text-xs text-muted-foreground sm:col-span-1">
                  Point
                  <select
                    class="w-full max-w-md rounded-lg border border-border bg-background px-3 py-2 text-sm"
                    .value=${dockPointId}
                    @change=${(e: Event) => {
                      dockPointId = (e.target as HTMLSelectElement).value;
                      paint();
                    }}
                  >
                    ${setpoints.length
                      ? setpoints.map(
                          (p) => html`<option value=${p.id}>${p.label} (${p.name})</option>`,
                        )
                      : html`<option value="">(no writable points)</option>`}
                  </select>
                </label>
                <label class="grid gap-1 text-xs text-muted-foreground">
                  New value
                  <input
                    type="number"
                    step="any"
                    inputmode="decimal"
                    autocomplete="off"
                    placeholder="e.g. 72"
                    class="max-w-[200px] rounded-lg border border-border bg-background px-3 py-2 text-sm"
                    .value=${dockValue}
                    @input=${(e: Event) => {
                      dockValue = (e.target as HTMLInputElement).value;
                    }}
                  />
                </label>
                <button
                  type="button"
                  class="rounded-lg border border-primary bg-primary/15 px-4 py-2 text-sm font-medium text-foreground hover:bg-primary/25 disabled:opacity-50"
                  ?disabled=${writing || !dockPointId}
                  @click=${() => void doWrite()}
                >
                  Write to BACnet
                </button>
              </div>
              <div class="mt-2 min-h-[1.25em] text-sm text-muted-foreground" role="status">
                ${writing ? "Writing…" : writeMessage}
              </div>
              <p class="mt-1 text-xs text-muted-foreground">
                This bar stays fixed while the overview above scrolls, similar to the App 7 dock outside the main scroll
                region.
              </p>
            </div>
          </aside>
        </div>
      `,
      outlet,
    );
    if (!loading && devices.length) {
      requestAnimationFrame(() => void drawPlotly(isDark));
    }
  };

  const drawPlotly = async (isDark: boolean) => {
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
    try {
      const Plotly = (await import("plotly.js-dist-min")).default as {
        react: (el: HTMLDivElement, data: unknown[], layout: unknown, config: unknown) => void;
      };
      if (cancelled) return;
      const inline = outlet.querySelector<HTMLDivElement>("#bas-inline-plot");
      const full = outlet.querySelector<HTMLDivElement>("#bas-full-plot");
      if (inline) Plotly.react(inline, trace, layout, config);
      if (plotFullscreen && full) Plotly.react(full, trace, layout, config);
    } catch {
      /* ignore */
    }
  };

  const selectDevice = async (id: string) => {
    selectedDeviceId = id;
    writeMessage = "";
    const nextPts = points.filter((p) => p.deviceId === id);
    if (nextPts[0]) selectedPointId = nextPts[0].id;
    await Promise.all([loadTrend(), loadSetpoints()]);
    syncDockPoint();
    paint();
  };

  const syncDockPoint = () => {
    if (!setpoints.length) {
      dockPointId = "";
      return;
    }
    if (!dockPointId || !setpoints.some((p) => p.id === dockPointId)) dockPointId = setpoints[0].id;
  };

  const syncSelection = () => {
    if (devices.length && (!selectedDeviceId || !devices.some((d) => d.id === selectedDeviceId))) {
      selectedDeviceId = devices[0].id;
    }
    const dpts = points.filter((p) => p.deviceId === selectedDeviceId);
    if (dpts.length && (!selectedPointId || !dpts.some((p) => p.id === selectedPointId))) {
      selectedPointId = dpts[0].id;
    }
  };

  const loadTrend = async () => {
    if (!selectedPointId) {
      trend = null;
      paint();
      return;
    }
    try {
      trend = await apiFetch<TrendResp>(`api/trends?pointId=${encodeURIComponent(selectedPointId)}`);
    } catch {
      trend = null;
    }
    paint();
  };

  const loadSetpoints = async () => {
    if (!selectedDeviceId) {
      setpoints = [];
      syncDockPoint();
      paint();
      return;
    }
    try {
      const res = await apiFetch<{ items: PointRow[] }>(
        `api/setpoints?deviceId=${encodeURIComponent(selectedDeviceId)}`,
      );
      setpoints = res.items ?? [];
    } catch {
      setpoints = [];
    }
    syncDockPoint();
    paint();
  };

  const loadAll = async () => {
    loading = true;
    paint();
    try {
      const [h, d, p, a, n] = await Promise.all([
        apiFetch<Health>("api/health"),
        apiFetch<{ items: Device[] }>("api/devices"),
        apiFetch<{ items: PointRow[] }>("api/points"),
        apiFetch<{ items: AlarmEvent[] }>("api/alarms/events"),
        apiFetch<NotificationsCfg>("api/notifications/config"),
      ]);
      if (cancelled) return;
      health = h;
      devices = d.items ?? [];
      points = p.items ?? [];
      alarms = a.items ?? [];
      notifications = n;
      syncSelection();
      await Promise.all([loadTrend(), loadSetpoints()]);
    } catch {
      if (!cancelled) {
        devices = [];
        points = [];
      }
    } finally {
      if (!cancelled) loading = false;
      paint();
    }
  };

  const doWrite = async () => {
    const n = Number(dockValue);
    if (dockValue === "" || Number.isNaN(n)) {
      writeMessage = "Enter a valid number.";
      paint();
      return;
    }
    writing = true;
    writeMessage = "";
    paint();
    try {
      const res = await apiFetch<{ status: string; pointName?: string; requestedValue?: unknown; message?: string }>(
        "api/setpoints/write",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ pointId: dockPointId, value: n }),
        },
      );
      if (res.status === "ok") {
        writeMessage = `Write succeeded: ${res.pointName ?? dockPointId} = ${String(res.requestedValue ?? "")}`;
        dockValue = "";
      } else {
        writeMessage = `Write failed: ${res.message ?? dockPointId}`;
      }
      await loadAll();
    } catch (e) {
      writeMessage = `Write failed: ${e instanceof Error ? e.message : "error"}`;
      paint();
    } finally {
      writing = false;
      paint();
    }
  };

  outlet.addEventListener("focusin", dockHandler);
  outlet.addEventListener("focusout", dockHandler);

  void loadAll();
  const unsub = subscribeTopics((topic) => {
    if (getGlobalPollPaused()) return;
    if (topic === "points.updated" || topic === "alarms.updated" || topic === "system.tick") {
      void loadAll();
    }
  });
  const iv = window.setInterval(() => {
    if (!getGlobalPollPaused()) void loadAll();
  }, 30_000);

  return () => {
    cancelled = true;
    window.clearInterval(iv);
    unsub();
    outlet.removeEventListener("focusin", dockHandler);
    outlet.removeEventListener("focusout", dockHandler);
    setGlobalPollDockFocus(false);
    render(html``, outlet);
  };
};
