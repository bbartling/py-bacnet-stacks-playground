import { html, render } from "lit-html";
import { apiFetch } from "../api";
import { subscribeTopics } from "../topics";
import { prettyJson } from "../util";
import type { MountFn } from "./types";

type Effective = {
  localTime: string;
  devices: { deviceId: string; deviceName: string; occupied: boolean; reason: string }[];
};

export const mountSchedule: MountFn = (outlet) => {
  let docJson = "";
  let effective: Effective | null = null;
  let loading = true;
  let saving = false;
  let message = "";
  let cancelled = false;

  const paint = () => {
    render(
      html`
        <div class="space-y-6">
          <div>
            <h1 class="text-2xl font-semibold tracking-tight">Occupancy schedule</h1>
            <p class="mt-1 text-sm text-muted-foreground">
              Edit the supervisory schedule document as JSON (replaces the React calendar/grid widget with a smaller
              operator surface). Use the API or prior exports for large edits, then save here.
            </p>
          </div>
          <div class="rounded-xl border border-border/60 bg-card/50 shadow-sm">
            <div class="space-y-3 p-6 pt-6">
              <div class="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  class="rounded bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground disabled:opacity-50"
                  ?disabled=${saving || loading}
                  @click=${() => void save()}
                >
                  ${saving ? "Saving…" : "Save schedule"}
                </button>
                <button
                  type="button"
                  class="rounded border border-border px-3 py-1.5 text-xs hover:bg-muted"
                  @click=${() => void load()}
                >
                  Reload
                </button>
              </div>
              ${message ? html`<p class="text-sm text-muted-foreground">${message}</p>` : null}
              ${loading
                ? html`<div class="h-64 w-full animate-pulse rounded-md bg-muted"></div>`
                : html`<textarea
                    class="min-h-[320px] w-full rounded-md border border-border bg-background p-3 font-mono text-xs"
                    .value=${docJson}
                    @input=${(e: Event) => {
                      docJson = (e.target as HTMLTextAreaElement).value;
                    }}
                    spellcheck=${false}
                  ></textarea>`}
            </div>
          </div>
          <div class="rounded-xl border border-border/60 bg-card/50 shadow-sm">
            <div class="p-6 pt-6">
              <h2 class="mb-2 text-sm font-semibold">Effective occupancy</h2>
              ${effective
                ? html`
                    <p class="mb-2 text-xs text-muted-foreground">Host local time: ${effective.localTime}</p>
                    <div class="max-h-[280px] overflow-auto rounded-md border border-border/50">
                      <table class="w-full border-collapse text-sm">
                        <thead>
                          <tr class="border-b border-border/60 bg-muted/40 text-left text-xs text-muted-foreground">
                            <th class="px-3 py-2 font-medium">Device</th>
                            <th class="px-3 py-2 font-medium">Occupied</th>
                            <th class="px-3 py-2 font-medium">Reason</th>
                          </tr>
                        </thead>
                        <tbody>
                          ${effective.devices.map(
                            (d) => html`
                              <tr class="border-b border-border/40 last:border-0">
                                <td class="px-3 py-2 font-mono text-xs">${d.deviceName}</td>
                                <td class="px-3 py-2">${d.occupied ? "yes" : "no"}</td>
                                <td class="px-3 py-2 text-xs text-muted-foreground">${d.reason}</td>
                              </tr>
                            `,
                          )}
                        </tbody>
                      </table>
                    </div>
                  `
                : html`<p class="text-sm text-muted-foreground">Loading effective schedule…</p>`}
            </div>
          </div>
        </div>
      `,
      outlet,
    );
  };

  const loadEffective = async () => {
    try {
      effective = await apiFetch<Effective>("api/schedule/effective");
    } catch {
      effective = null;
    }
    paint();
  };

  const load = async () => {
    loading = true;
    message = "";
    paint();
    try {
      const doc = await apiFetch<unknown>("api/schedule");
      if (cancelled) return;
      docJson = prettyJson(doc);
    } catch (e) {
      if (!cancelled) {
        docJson = "";
        message = e instanceof Error ? e.message : "Load failed";
      }
    } finally {
      if (!cancelled) loading = false;
      paint();
    }
    await loadEffective();
  };

  const save = async () => {
    saving = true;
    message = "";
    paint();
    try {
      const body = JSON.parse(docJson) as unknown;
      const res = await apiFetch<{ status?: string; bacnetScheduleSync?: { ok?: boolean; message?: string } }>(
        "api/schedule",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
      );
      message = `Saved (${res.status ?? "ok"})${res.bacnetScheduleSync?.message ? ` — ${res.bacnetScheduleSync.message}` : ""}`;
      await loadEffective();
    } catch (e) {
      message = e instanceof Error ? e.message : "Save failed";
    } finally {
      saving = false;
      paint();
    }
  };

  void load();
  const unsub = subscribeTopics((topic) => {
    if (topic === "schedule.updated") void loadEffective();
  });

  return () => {
    cancelled = true;
    unsub();
    render(html``, outlet);
  };
};
