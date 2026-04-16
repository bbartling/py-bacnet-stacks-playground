import { html, render } from "lit-html";
import { apiFetch } from "../api";
import { subscribeTopics } from "../topics";
import type { MountFn } from "./types";

type Event = {
  id: string;
  severity: string;
  state: string;
  message: string;
  triggeredAt: string;
  deviceId: string;
  pointId: string;
};

export const mountFaults: MountFn = (outlet) => {
  let items: Event[] = [];
  let loading = true;
  let cancelled = false;

  const paint = () => {
    render(
      html`
        <div class="space-y-4">
          <div>
            <h1 class="text-2xl font-semibold tracking-tight">Faults</h1>
            <p class="mt-1 text-sm text-muted-foreground">
              Fault analytics view for rule outcomes and diagnostics. Active alarm workflow is on the Alarms tab.
            </p>
          </div>
          <div class="rounded-xl border border-border/60 bg-card/50 shadow-sm">
            <div class="p-6 pt-6">
              ${loading
                ? html`<div class="h-64 w-full animate-pulse rounded-xl bg-muted"></div>`
                : html`
                    <div class="max-h-[min(60vh,560px)] overflow-auto rounded-md border border-border/50">
                      <table class="w-full border-collapse text-sm">
                        <thead>
                          <tr class="border-b border-border/60 bg-muted/40 text-left text-xs text-muted-foreground">
                            <th class="px-3 py-2 font-medium">Severity</th>
                            <th class="px-3 py-2 font-medium">Message</th>
                            <th class="px-3 py-2 font-medium">Point</th>
                            <th class="px-3 py-2 font-medium">When</th>
                          </tr>
                        </thead>
                        <tbody>
                          ${items.map(
                            (e) => html`
                              <tr class="border-b border-border/40 last:border-0">
                                <td class="px-3 py-2 text-xs font-medium uppercase">${e.severity}</td>
                                <td class="px-3 py-2 text-sm">${e.message}</td>
                                <td class="px-3 py-2 font-mono text-xs">${e.pointId}</td>
                                <td class="px-3 py-2 text-xs text-muted-foreground">${e.triggeredAt}</td>
                              </tr>
                            `,
                          )}
                        </tbody>
                      </table>
                    </div>
                    ${items.length === 0
                      ? html`<p class="py-6 text-center text-sm text-muted-foreground">No active alarm events.</p>`
                      : null}
                  `}
            </div>
          </div>
        </div>
      `,
      outlet,
    );
  };

  const load = async () => {
    loading = true;
    paint();
    try {
      const res = await apiFetch<{ items: Event[] }>("api/alarms/events");
      if (cancelled) return;
      items = res.items ?? [];
    } catch {
      if (!cancelled) items = [];
    } finally {
      if (!cancelled) loading = false;
      paint();
    }
  };

  void load();
  const unsub = subscribeTopics((topic) => {
    if (topic === "alarms.updated") void load();
  });
  const iv = window.setInterval(() => void load(), 15_000);
  paint();

  return () => {
    cancelled = true;
    window.clearInterval(iv);
    unsub();
    render(html``, outlet);
  };
};
