import { html, render } from "lit-html";
import { apiFetch } from "../api";
import { subscribeTopics } from "../topics";
import type { MountFn } from "./types";

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

export const mountLivePoints: MountFn = (outlet) => {
  let points: PointRow[] = [];
  let loading = true;
  let filter = "";
  let expanded: Record<string, boolean> = {};
  let edit: { pointId: string; value: string } | null = null;
  let writeErr: string | null = null;
  let cancelled = false;

  const byDevice = (): Map<string, PointRow[]> => {
    const m = new Map<string, PointRow[]>();
    const q = filter.trim().toLowerCase();
    for (const p of points) {
      if (q) {
        const hay = `${p.deviceId} ${p.label} ${p.name}`.toLowerCase();
        if (!hay.includes(q)) continue;
      }
      const list = m.get(p.deviceId) ?? [];
      list.push(p);
      m.set(p.deviceId, list);
    }
    return m;
  };

  const syncExpanded = () => {
    const next: Record<string, boolean> = {};
    for (const d of byDevice().keys()) next[d] = expanded[d] ?? true;
    expanded = next;
  };

  const paint = () => {
    syncExpanded();
    const groups = [...byDevice().entries()];
    render(
      html`
        <div class="space-y-6">
          <div>
            <h1 class="text-2xl font-semibold tracking-tight">Live points</h1>
            <p class="mt-1 text-sm text-muted-foreground">
              Point tree by device with live values and writable setpoints using BACnet JSON-RPC.
            </p>
            <input
              class="mt-3 w-full max-w-md rounded border border-border bg-background px-2 py-1 text-sm"
              placeholder="Filter device/point..."
              .value=${filter}
              @input=${(e: Event) => {
                filter = (e.target as HTMLInputElement).value;
                paint();
              }}
            />
          </div>
          ${loading
            ? html`<div class="h-96 w-full animate-pulse rounded-xl bg-muted"></div>`
            : html`
                ${groups.map(([deviceId, rows]) => {
                  const open = expanded[deviceId] ?? true;
                  return html`
                    <div class="rounded-xl border border-border/60 bg-card/50 shadow-sm">
                      <div class="p-6 pt-6">
                        <button
                          type="button"
                          class="mb-3 inline-flex items-center gap-2 text-left text-sm font-semibold"
                          @click=${() => {
                            expanded = { ...expanded, [deviceId]: !open };
                            paint();
                          }}
                        >
                          <span>${open ? "▾" : "▸"}</span>
                          <span>${deviceId}</span>
                          <span class="text-xs text-muted-foreground">(${rows.length} points)</span>
                        </button>
                        ${open
                          ? html`
                              <div class="overflow-x-auto rounded-md border border-border/50">
                                <table class="w-full border-collapse text-sm">
                                  <thead>
                                    <tr class="border-b border-border/60 bg-muted/40 text-left text-xs">
                                      <th class="px-3 py-2 font-medium text-muted-foreground">Point</th>
                                      <th class="px-3 py-2 font-medium text-muted-foreground">Value</th>
                                      <th class="px-3 py-2 font-medium text-muted-foreground">Updated</th>
                                      <th class="px-3 py-2 font-medium text-muted-foreground">Alarm</th>
                                      <th class="px-3 py-2 text-right font-medium text-muted-foreground">Write</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    ${rows.map((p) => {
                                      const editing = edit?.pointId === p.id;
                                      return html`
                                        <tr class="border-b border-border/40 last:border-0">
                                          <td class="px-3 py-2">
                                            <div class="font-medium">${p.label}</div>
                                            <div class="font-mono text-xs text-muted-foreground">${p.name}</div>
                                          </td>
                                          <td class="px-3 py-2 font-mono text-sm">
                                            ${String(p.value ?? "—")} ${p.units}
                                          </td>
                                          <td class="px-3 py-2 text-xs text-muted-foreground">
                                            ${p.lastUpdated ?? "—"}
                                          </td>
                                          <td class="px-3 py-2 text-xs">${p.alarmState}</td>
                                          <td class="px-3 py-2 text-right">
                                            ${p.adjustable
                                              ? editing
                                                ? html`<span class="inline-flex gap-1">
                                                    <input
                                                      class="w-24 rounded border border-border bg-background px-2 py-1 text-xs"
                                                      .value=${edit?.value ?? ""}
                                                    />
                                                    <button
                                                      type="button"
                                                      class="rounded bg-primary px-2 py-1 text-xs text-primary-foreground"
                                                      @click=${(e: Event) => {
                                                        const inp = (e.target as HTMLElement)
                                                          .previousElementSibling as HTMLInputElement | null;
                                                        void sendWrite(p.id, inp?.value ?? "");
                                                      }}
                                                    >
                                                      Send
                                                    </button>
                                                  </span>`
                                                : html`<button
                                                    type="button"
                                                    class="text-xs text-primary hover:underline"
                                                    @click=${() => {
                                                      edit = { pointId: p.id, value: String(p.value ?? "") };
                                                      paint();
                                                    }}
                                                  >
                                                    Edit
                                                  </button>`
                                              : html`<span class="text-xs text-muted-foreground">—</span>`}
                                          </td>
                                        </tr>
                                      `;
                                    })}
                                  </tbody>
                                </table>
                              </div>
                            `
                          : null}
                      </div>
                    </div>
                  `;
                })}
                ${writeErr ? html`<p class="text-sm text-destructive">${writeErr}</p>` : null}
              `}
        </div>
      `,
      outlet,
    );
  };

  const sendWrite = async (pointId: string, raw: string) => {
    writeErr = null;
    const n = Number(raw);
    if (raw === "" || Number.isNaN(n)) {
      writeErr = "Enter a valid number.";
      paint();
      return;
    }
    try {
      await apiFetch("api/setpoints/write", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pointId, value: n }),
      });
      edit = null;
      await load();
    } catch (e) {
      writeErr = e instanceof Error ? e.message : "Write failed";
      paint();
    }
  };

  const load = async () => {
    loading = true;
    paint();
    try {
      const res = await apiFetch<{ items: PointRow[] }>("api/points");
      if (cancelled) return;
      points = res.items ?? [];
    } catch {
      if (!cancelled) points = [];
    } finally {
      if (!cancelled) loading = false;
      paint();
    }
  };

  void load();
  const unsub = subscribeTopics((topic) => {
    if (topic === "points.updated") void load();
  });
  paint();

  return () => {
    cancelled = true;
    unsub();
    render(html``, outlet);
  };
};
