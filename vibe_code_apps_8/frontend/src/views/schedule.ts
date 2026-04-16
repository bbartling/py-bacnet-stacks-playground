import { html, render } from "lit-html";
import { apiFetch } from "../api";
import { subscribeTopics } from "../topics";
import { prettyJson } from "../util";
import type { ApiScheduleDoc } from "../schedule-widget/scheduleApiBridge";
import { mountScheduleIsland, unmountScheduleIsland } from "../schedule-widget/bootstrap";
import type { MountFn } from "./types";

type EffectiveDevice = {
  deviceId: string;
  deviceName: string;
  occupied: boolean;
  reason: string;
  scheduleId?: string | null;
  scheduleLabel?: string | null;
};

type Effective = {
  localTime: string;
  devices: EffectiveDevice[];
};

export const mountSchedule: MountFn = (outlet) => {
  let cancelled = false;
  let loadError: string | null = null;
  let effective: Effective | null = null;
  let effectiveError: string | null = null;
  let effectiveReady = false;
  let advancedOpen = false;
  let docJson = "";
  let advSaving = false;
  let advMessage = "";

  const reactHost = document.createElement("div");
  reactHost.className = "min-h-[320px] rounded-xl border border-border/60 bg-card/30";

  const effectiveHost = document.createElement("div");

  const advancedHost = document.createElement("div");

  const shell = document.createElement("div");
  shell.className = "space-y-6";

  const header = document.createElement("div");
  header.innerHTML = `
    <div>
      <h1 class="text-2xl font-semibold tracking-tight">Occupancy schedule</h1>
      <p class="mt-1 text-sm text-muted-foreground">
        Visual editor (weekly calendar, operating week, holidays, BACnet points) syncs with the same
        <code class="rounded bg-muted px-1">schedule.json</code> document as the API. Use <strong>Reload</strong> after external edits.
      </p>
    </div>
    <div class="mt-3 flex flex-wrap items-center gap-2">
      <button type="button" id="schedule-reload" class="rounded border border-border px-3 py-1.5 text-xs hover:bg-muted">
        Reload
      </button>
    </div>
  `;

  shell.appendChild(header);
  shell.appendChild(reactHost);
  shell.appendChild(effectiveHost);
  shell.appendChild(advancedHost);
  outlet.appendChild(shell);

  header.querySelector("#schedule-reload")?.addEventListener("click", () => void fullReload());

  const paintAdvanced = () => {
    render(
      html`
        <details
          class="rounded-xl border border-border/60 bg-card/50 shadow-sm"
          ?open=${advancedOpen}
          @toggle=${(e: Event) => {
            advancedOpen = (e.target as HTMLDetailsElement).open;
          }}
        >
          <summary class="cursor-pointer select-none px-4 py-3 text-sm font-semibold">Advanced: raw JSON</summary>
          <div class="space-y-3 border-t border-border/50 p-4 pt-4">
            <p class="text-xs text-muted-foreground">
              Paste a full v2 schedule document. Invalid JSON will be rejected. After save, the visual editor reloads from the server.
            </p>
            <textarea
              class="min-h-[240px] w-full rounded-md border border-border bg-background p-3 font-mono text-xs"
              .value=${docJson}
              @input=${(e: Event) => {
                docJson = (e.target as HTMLTextAreaElement).value;
              }}
              spellcheck=${false}
            ></textarea>
            <div class="flex flex-wrap items-center gap-2">
              <button
                type="button"
                class="rounded bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground disabled:opacity-50"
                ?disabled=${advSaving}
                @click=${() => void saveAdvanced()}
              >
                ${advSaving ? "Saving…" : "Save JSON"}
              </button>
            </div>
            ${advMessage ? html`<p class="text-sm text-muted-foreground">${advMessage}</p>` : null}
          </div>
        </details>
      `,
      advancedHost,
    );
  };

  const paintEffective = () => {
    render(
      html`
        <div class="rounded-xl border border-border/60 bg-card/50 shadow-sm">
          <div class="p-6 pt-6">
            <h2 class="mb-2 text-sm font-semibold">Effective occupancy</h2>
            ${!effectiveReady
              ? html`<p class="text-sm text-muted-foreground">Loading effective schedule…</p>`
              : effectiveError
                ? html`<p class="text-sm text-destructive">${effectiveError}</p>`
                : effective
                  ? html`
                      <p class="mb-2 text-xs text-muted-foreground">Host local time: ${effective.localTime}</p>
                      <div class="max-h-[320px] overflow-auto rounded-md border border-border/50">
                        <table class="w-full border-collapse text-sm">
                          <thead>
                            <tr class="border-b border-border/60 bg-muted/40 text-left text-xs text-muted-foreground">
                              <th class="px-3 py-2 font-medium">Device</th>
                              <th class="px-3 py-2 font-medium">Schedule</th>
                              <th class="px-3 py-2 font-medium">Occupied</th>
                              <th class="px-3 py-2 font-medium">Reason</th>
                            </tr>
                          </thead>
                          <tbody>
                            ${effective.devices.map(
                              (d) => html`
                                <tr class="border-b border-border/40 last:border-0">
                                  <td class="px-3 py-2 font-mono text-xs">${d.deviceName}</td>
                                  <td class="px-3 py-2 text-xs text-muted-foreground">
                                    ${d.scheduleLabel ?? d.scheduleId ?? "—"}
                                  </td>
                                  <td class="px-3 py-2">${d.occupied ? "yes" : "no"}</td>
                                  <td class="px-3 py-2 text-xs text-muted-foreground">${d.reason}</td>
                                </tr>
                              `,
                            )}
                          </tbody>
                        </table>
                      </div>
                    `
                  : html`<p class="text-sm text-muted-foreground">No effective occupancy data.</p>`}
          </div>
        </div>
      `,
      effectiveHost,
    );
  };

  const mountEditor = (doc: ApiScheduleDoc) => {
    unmountScheduleIsland();
    mountScheduleIsland(reactHost, {
      initialDoc: doc,
      onSave: async (next) => {
        await apiFetch("api/schedule", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(next),
        });
      },
      onAfterSave: () => void loadEffective(),
    });
  };

  const loadEffective = async () => {
    effectiveReady = false;
    effectiveError = null;
    paintEffective();
    try {
      effective = await apiFetch<Effective>("api/schedule/effective");
      effectiveError = null;
    } catch (e) {
      effective = null;
      effectiveError = e instanceof Error ? e.message : "Failed to load effective schedule";
    } finally {
      effectiveReady = true;
      paintEffective();
    }
  };

  const fullReload = async () => {
    loadError = null;
    unmountScheduleIsland();
    paintAdvanced();
    paintEffective();
    try {
      const doc = await apiFetch<ApiScheduleDoc>("api/schedule");
      if (cancelled) return;
      docJson = prettyJson(doc);
      mountEditor(doc);
    } catch (e) {
      if (!cancelled) {
        loadError = e instanceof Error ? e.message : "Load failed";
        reactHost.replaceChildren();
        const p = document.createElement("p");
        p.className = "text-destructive p-4 text-sm";
        p.textContent = loadError;
        reactHost.appendChild(p);
      }
    }
    await loadEffective();
    paintAdvanced();
  };

  const saveAdvanced = async () => {
    advSaving = true;
    advMessage = "";
    paintAdvanced();
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
      advMessage = `Saved (${res.status ?? "ok"})${res.bacnetScheduleSync?.message ? ` — ${res.bacnetScheduleSync.message}` : ""}`;
      await fullReload();
    } catch (e) {
      advMessage = e instanceof Error ? e.message : "Save failed";
    } finally {
      advSaving = false;
      paintAdvanced();
    }
  };

  void fullReload();

  const unsub = subscribeTopics((topic) => {
    if (topic === "schedule.updated") void loadEffective();
  });

  return () => {
    cancelled = true;
    unsub();
    unmountScheduleIsland();
    render(html``, effectiveHost);
    render(html``, advancedHost);
    outlet.replaceChildren();
  };
};
