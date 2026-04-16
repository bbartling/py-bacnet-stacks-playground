import { html, render } from "lit-html";
import { apiFetch } from "../api";
import type { MountFn } from "./types";

type ListResp = { items: string[]; stderr: string; exitCode: number };
type GetResp = { name: string; content: string; stderr: string; exitCode: number };

function groupConfigs(names: string[]): Record<string, string[]> {
  const root: Record<string, string[]> = {};
  for (const n of names) {
    const seg = n.split("/")[0] || "_";
    root[seg] = root[seg] ?? [];
    root[seg].push(n);
  }
  for (const k of Object.keys(root)) root[k].sort();
  return root;
}

export const mountDriver: MountFn = (outlet) => {
  let list: string[] = [];
  let selected: string | null = null;
  let text = "";
  let isCsv = false;
  let stderr = "";
  let loadingList = true;
  let fetchingDetail = false;
  let cancelled = false;

  const paint = () => {
    const grouped = groupConfigs(list);
    render(
      html`
        <div class="space-y-4">
          <div>
            <h1 class="text-2xl font-semibold tracking-tight">Driver config files</h1>
            <p class="mt-1 text-sm text-muted-foreground">
              Files under the API container <code class="rounded bg-muted px-1">/data/driver_configs</code> (JSON/CSV).
              Use this tree for site-specific BACnet registry exports, notes, or JSON you want beside SQLite. For live
              polling, configure devices and points in easy-aso (<code class="rounded bg-muted px-1">/api/v1</code> or
              <code class="rounded bg-muted px-1">/docs</code>) and restart the API container if you change wiring.
            </p>
          </div>
          <div class="grid gap-4 lg:grid-cols-5">
            <div class="rounded-xl border border-border/60 bg-card/50 shadow-sm lg:col-span-2">
              <div class="max-h-[560px] overflow-auto p-6 pt-6">
                ${loadingList
                  ? html`<div class="h-[520px] w-full animate-pulse rounded-xl bg-muted"></div>`
                  : html`
                      ${Object.entries(grouped).map(
                        ([group, names]) => html`
                          <div class="mb-4">
                            <p class="mb-1 text-xs font-semibold uppercase text-muted-foreground">${group}</p>
                            <ul class="space-y-0.5">
                              ${names.map(
                                (n) => html`
                                  <li>
                                    <button
                                      type="button"
                                      class=${`w-full rounded px-2 py-1 text-left font-mono text-xs hover:bg-muted ${
                                        selected === n ? "bg-muted font-medium" : ""
                                      }`}
                                      @click=${() => void pick(n)}
                                    >
                                      ${n}
                                    </button>
                                  </li>
                                `,
                              )}
                            </ul>
                          </div>
                        `,
                      )}
                    `}
              </div>
            </div>
            <div class="rounded-xl border border-border/60 bg-card/50 shadow-sm lg:col-span-3">
              <div class="space-y-3 p-6 pt-6">
                <div class="flex flex-wrap items-center gap-3">
                  <p class="text-sm font-medium">${selected ?? "Select a config"}</p>
                  <label class="flex items-center gap-2 text-xs">
                    <input
                      type="checkbox"
                      .checked=${isCsv}
                      @change=${(e: Event) => {
                        isCsv = (e.target as HTMLInputElement).checked;
                        paint();
                      }}
                    />
                    Store as CSV (<code>--csv</code>)
                  </label>
                  <button
                    type="button"
                    class="rounded bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground disabled:opacity-50"
                    ?disabled=${!selected}
                    @click=${() => void save()}
                  >
                    Save to config store
                  </button>
                  <button
                    type="button"
                    class="rounded border border-destructive px-3 py-1.5 text-xs text-destructive disabled:opacity-50"
                    ?disabled=${!selected}
                    @click=${() => void del()}
                  >
                    Delete…
                  </button>
                </div>
                ${fetchingDetail ? html`<div class="h-80 w-full animate-pulse rounded-md bg-muted"></div>` : null}
                <textarea
                  class="min-h-[360px] w-full rounded-md border border-border bg-background p-3 font-mono text-xs"
                  .value=${text}
                  @input=${(e: Event) => {
                    text = (e.target as HTMLTextAreaElement).value;
                  }}
                  spellcheck=${false}
                ></textarea>
                ${stderr
                  ? html`<pre class="rounded bg-destructive/10 p-2 text-xs whitespace-pre-wrap">${stderr}</pre>`
                  : null}
              </div>
            </div>
          </div>
        </div>
      `,
      outlet,
    );
  };

  const loadList = async () => {
    loadingList = true;
    paint();
    try {
      const res = await apiFetch<ListResp>("api/driver/configs");
      if (cancelled) return;
      list = res.items ?? [];
      stderr = res.stderr ?? "";
    } catch {
      if (!cancelled) list = [];
    } finally {
      if (!cancelled) loadingList = false;
      paint();
    }
  };

  const pick = async (name: string) => {
    selected = name;
    fetchingDetail = true;
    paint();
    try {
      const res = await apiFetch<GetResp>(`api/driver/config?name=${encodeURIComponent(name)}`);
      if (cancelled) return;
      text = res.content ?? "";
      stderr = res.stderr ?? "";
      isCsv = Boolean(name.endsWith(".csv") || name.startsWith("registry_configs/"));
    } catch {
      if (!cancelled) text = "";
    } finally {
      if (!cancelled) fetchingDetail = false;
      paint();
    }
  };

  const save = async () => {
    if (!selected) return;
    await apiFetch("api/driver/config/store", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: selected, content: text, csv: isCsv }),
    });
    await pick(selected);
  };

  const del = async () => {
    if (!selected) return;
    if (!window.confirm(`Delete config "${selected}" from BAS Lite driver storage?`)) return;
    await apiFetch("api/driver/config/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: selected }),
    });
    selected = null;
    text = "";
    stderr = "";
    await loadList();
  };

  void loadList();
  const iv = window.setInterval(() => void loadList(), 30_000);

  return () => {
    cancelled = true;
    window.clearInterval(iv);
    render(html``, outlet);
  };
};
