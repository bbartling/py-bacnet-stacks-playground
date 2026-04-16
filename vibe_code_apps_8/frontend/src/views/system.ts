import { html, render } from "lit-html";
import { apiFetch, apiUrl } from "../api";
import { subscribeTopics } from "../topics";
import type { MountFn } from "./types";

type Metrics = {
  timestamp: string;
  cpuPercent: number | null;
  loadavg: { load1: number | null; load5: number | null; load15: number | null };
  memory: { memTotalBytes: number | null; memAvailableBytes: number | null; memUsedBytes: number | null };
  diskRoot: {
    totalBytes: number | null;
    usedBytes: number | null;
    freeBytes: number | null;
    usedPercent: number | null;
  };
  hostname: string | null;
};

type Vctl = {
  exitCode: number;
  stdout: string;
  stderr: string;
  agents: { uuid: string; summary: string }[];
};

type ContainerRow = {
  id: string;
  name: string;
  service: string;
  status: string;
  image: string;
  easyAsoAgentModule?: string;
  easyAsoAgentClass?: string;
  easyAsoRole?: string;
};

type ContainersResponse = {
  dockerAvailable: boolean;
  items: ContainerRow[];
  message?: string;
};

type ContainerLogs = {
  dockerAvailable: boolean;
  name: string;
  logs: string;
  message?: string;
};

type Messaging = {
  bacnetOnline: boolean;
  bacnetRpcUrl: string;
  mqttBridgeOnline: boolean;
  mqttBrokerUrl: string;
  note: string;
  error?: string;
};

function fmtGb(bytes: number | null | undefined): string {
  if (bytes == null) return "—";
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}

function displayContainerName(name: string): string {
  return name.replace(/^\//, "");
}

export const mountSystem: MountFn = (outlet) => {
  let metrics: Metrics | null = null;
  let vctl: Vctl | null = null;
  let containers: ContainersResponse | null = null;
  let messaging: Messaging | null = null;
  let logs: ContainerLogs | null = null;
  let selectedContainer = "";
  let liveLogLines: string[] = [];
  let streamStatus: "idle" | "connecting" | "live" | "error" = "idle";
  let menu: { x: number; y: number; uuid: string; summary: string } | null = null;
  let lifecycleErr: string | null = null;
  let lifecycleOut: string | null = null;
  let loading = true;
  let es: EventSource | null = null;

  const paint = () => {
    const easyAsoContainers = (containers?.items ?? []).filter(
      (c) =>
        Boolean(c.easyAsoRole) ||
        (c.service ?? "").startsWith("easy-aso-agent") ||
        (c.easyAsoAgentModule ?? "").startsWith("agents."),
    );
    const renderedLogs =
      liveLogLines.length > 0 ? liveLogLines.join("\n") : logs?.logs || logs?.message || "No logs.";

    render(
      html`
        <div class="space-y-6" @click=${() => closeMenu()}>
          <div>
            <h1 class="text-2xl font-semibold tracking-tight">System</h1>
            <p class="mt-1 text-sm text-muted-foreground">
              Raspberry Pi resources from the API container. Container status is summarized here, and deeper service
              checks still belong to <code class="rounded bg-muted px-1">docker compose ps</code> and logs on the host.
            </p>
          </div>
          <div class="grid gap-4 lg:grid-cols-3">
            <div class="rounded-xl border border-border/60 bg-card/50 shadow-sm lg:col-span-1">
              <div class="space-y-3 p-6 pt-6 text-sm">
                <p class="text-xs font-medium uppercase text-muted-foreground">Host</p>
                ${loading && !metrics
                  ? html`<div class="h-24 w-full animate-pulse rounded-md bg-muted"></div>`
                  : html`
                      <p class="font-mono text-base">${metrics?.hostname ?? "—"}</p>
                      <p>
                        CPU:
                        <span class="font-medium">
                          ${metrics?.cpuPercent != null ? `${metrics.cpuPercent}%` : "n/a"}
                        </span>
                      </p>
                      <p class="text-muted-foreground">
                        Load (1/5/15): ${metrics?.loadavg.load1 ?? "—"} / ${metrics?.loadavg.load5 ?? "—"} /
                        ${metrics?.loadavg.load15 ?? "—"}
                      </p>
                      <p>
                        RAM used: ${fmtGb(metrics?.memory.memUsedBytes)} /
                        ${fmtGb(metrics?.memory.memTotalBytes)}
                      </p>
                      <p>
                        Disk (/): ${metrics?.diskRoot.usedPercent ?? "—"}% used · free
                        ${fmtGb(metrics?.diskRoot.freeBytes)}
                      </p>
                    `}
              </div>
            </div>
            <div class="rounded-xl border border-border/60 bg-card/50 shadow-sm lg:col-span-2">
              <div class="p-6 pt-6">
                <div class="mb-2 flex flex-wrap items-center justify-between gap-2">
                  <p class="text-xs font-medium uppercase text-muted-foreground">Container and edge status</p>
                  <button
                    type="button"
                    class="rounded border border-border px-2 py-1 text-xs hover:bg-muted"
                    @click=${() => void loadVctl()}
                  >
                    Refresh
                  </button>
                </div>
                ${!vctl
                  ? html`<div class="h-48 w-full animate-pulse rounded-md bg-muted"></div>`
                  : html`
                      <div class="max-h-[420px] overflow-auto rounded-md border border-border/60">
                        <table class="w-full border-collapse text-sm">
                          <thead>
                            <tr class="border-b border-border/60 bg-muted/40 text-left text-xs text-muted-foreground">
                              <th class="px-3 py-2 font-medium">Identifier</th>
                              <th class="px-3 py-2 font-medium">Summary</th>
                            </tr>
                          </thead>
                          <tbody>
                            ${vctl.agents.map(
                              (a) => html`
                                <tr
                                  class="cursor-context-menu border-b border-border/40 last:border-0"
                                  @contextmenu=${(e: MouseEvent) => {
                                    e.preventDefault();
                                    menu = { x: e.clientX, y: e.clientY, uuid: a.uuid, summary: a.summary };
                                    paint();
                                  }}
                                >
                                  <td class="px-3 py-2 font-mono text-xs">${a.uuid}</td>
                                  <td class="px-3 py-2 text-xs">${a.summary}</td>
                                </tr>
                              `,
                            )}
                          </tbody>
                        </table>
                        ${vctl.stderr
                          ? html`<pre
                              class="border-t border-border/60 bg-destructive/10 p-2 text-xs whitespace-pre-wrap"
                            >${vctl.stderr}</pre>`
                          : null}
                      </div>
                    `}
                <p class="mt-2 text-xs text-muted-foreground">
                  Status endpoint: <code class="rounded bg-muted px-1">${apiUrl("api/agents/vctl")}</code>
                </p>
              </div>
            </div>
          </div>
          <div class="grid gap-4 lg:grid-cols-3">
            <div class="rounded-xl border border-border/60 bg-card/50 shadow-sm lg:col-span-1">
              <div class="space-y-3 p-6 pt-6 text-sm">
                <p class="text-xs font-medium uppercase text-muted-foreground">BACnet + MQTT</p>
                ${!messaging
                  ? html`<div class="h-20 w-full animate-pulse rounded-md bg-muted"></div>`
                  : html`
                      <p>
                        BACnet online:
                        <span
                          class=${messaging.bacnetOnline ? "font-medium text-emerald-600" : "font-medium text-destructive"}
                        >
                          ${messaging.bacnetOnline ? "yes" : "no"}
                        </span>
                      </p>
                      <p class="font-mono text-xs text-muted-foreground">${messaging.bacnetRpcUrl}</p>
                      <p>
                        MQTT bridge:
                        <span class="font-medium">${messaging.mqttBridgeOnline ? "online" : "planned / offline"}</span>
                      </p>
                      <p class="text-xs text-muted-foreground">${messaging.note}</p>
                    `}
              </div>
            </div>
            <div class="rounded-xl border border-border/60 bg-card/50 shadow-sm lg:col-span-2">
              <div class="p-6 pt-6">
                <div class="mb-2 flex flex-wrap items-center justify-between gap-2">
                  <p class="text-xs font-medium uppercase text-muted-foreground">Docker stack (compose project)</p>
                  <button
                    type="button"
                    class="rounded border border-border px-2 py-1 text-xs hover:bg-muted"
                    @click=${() => void loadContainers()}
                  >
                    Refresh
                  </button>
                </div>
                ${!containers
                  ? html`<div class="h-48 w-full animate-pulse rounded-md bg-muted"></div>`
                  : !containers.dockerAvailable
                    ? html`<p class="text-sm text-muted-foreground">
                        Docker socket unavailable in API container. Endpoint:
                        <code class="rounded bg-muted px-1">${apiUrl("api/system/containers")}</code>
                      </p>`
                    : html`
                        <div class="max-h-[280px] overflow-auto rounded-md border border-border/60">
                          <table class="w-full border-collapse text-sm">
                            <thead>
                              <tr class="border-b border-border/60 bg-muted/40 text-left text-xs text-muted-foreground">
                                <th class="px-3 py-2 font-medium">Name</th>
                                <th class="px-3 py-2 font-medium">Service</th>
                                <th class="px-3 py-2 font-medium">Role</th>
                                <th class="px-3 py-2 font-medium">Agent</th>
                                <th class="px-3 py-2 font-medium">Status</th>
                                <th class="px-3 py-2 text-right font-medium">Actions</th>
                              </tr>
                            </thead>
                            <tbody>
                              ${containers.items.map(
                                (c) => html`
                                  <tr class="border-b border-border/40 last:border-0">
                                    <td class="px-3 py-2 font-mono text-xs">${displayContainerName(c.name)}</td>
                                    <td class="px-3 py-2 text-xs">${c.service || "—"}</td>
                                    <td class="px-3 py-2 text-xs">
                                      ${c.easyAsoRole
                                        ? html`<span
                                            class="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground"
                                            >${c.easyAsoRole}</span
                                          >`
                                        : "—"}
                                    </td>
                                    <td class="px-3 py-2 text-xs text-muted-foreground">
                                      ${[c.easyAsoAgentModule, c.easyAsoAgentClass].filter(Boolean).join(":") || "—"}
                                    </td>
                                    <td class="px-3 py-2 text-xs">${c.status}</td>
                                    <td class="space-x-2 whitespace-nowrap px-3 py-2 text-right">
                                      <button
                                        type="button"
                                        class="text-xs text-primary hover:underline"
                                        @click=${() => selectLogs(c.name)}
                                      >
                                        logs
                                      </button>
                                      <button
                                        type="button"
                                        class="text-xs text-muted-foreground hover:underline"
                                        @click=${() => void containerAction(c.name, "restart")}
                                      >
                                        restart
                                      </button>
                                      <button
                                        type="button"
                                        class="text-xs text-muted-foreground hover:underline"
                                        @click=${() => void containerAction(c.name, "stop")}
                                      >
                                        stop
                                      </button>
                                      <button
                                        type="button"
                                        class="text-xs text-muted-foreground hover:underline"
                                        @click=${() => void containerAction(c.name, "start")}
                                      >
                                        start
                                      </button>
                                    </td>
                                  </tr>
                                `,
                              )}
                            </tbody>
                          </table>
                        </div>
                      `}
              </div>
            </div>
          </div>
          ${easyAsoContainers.length
            ? html`
                <div class="rounded-xl border border-border/60 bg-card/50 shadow-sm">
                  <div class="space-y-2 p-6 pt-6">
                    <p class="text-xs font-medium uppercase text-muted-foreground">Easy ASO agent logs</p>
                    <div class="flex flex-wrap gap-2">
                      ${easyAsoContainers.map((c) => {
                        const label = c.easyAsoRole || c.service || displayContainerName(c.name);
                        const active = selectedContainer === c.name;
                        return html`
                          <button
                            type="button"
                            class=${`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                              active ? "border-primary bg-primary/10 text-primary" : "border-border hover:bg-muted"
                            }`}
                            @click=${() => {
                              liveLogLines = [];
                              selectedContainer = c.name;
                              wireSse();
                              void loadLogs();
                              paint();
                            }}
                          >
                            ${label}
                          </button>
                        `;
                      })}
                    </div>
                  </div>
                </div>
              `
            : null}
          ${selectedContainer
            ? html`
                <div class="rounded-xl border border-border/60 bg-card/50 shadow-sm">
                  <div class="p-6 pt-6">
                    <div class="mb-2 flex items-center justify-between gap-2">
                      <p class="text-xs font-medium uppercase text-muted-foreground">
                        Container logs:
                        <span class="normal-case font-mono">${displayContainerName(selectedContainer)}</span>
                      </p>
                      <div class="flex items-center gap-2">
                        <span
                          class=${`text-xs ${
                            streamStatus === "live"
                              ? "text-emerald-600"
                              : streamStatus === "error"
                                ? "text-destructive"
                                : "text-muted-foreground"
                          }`}
                        >
                          ${streamStatus === "live"
                            ? "streaming live"
                            : streamStatus === "connecting"
                              ? "connecting…"
                              : streamStatus}
                        </span>
                        <button
                          type="button"
                          class="rounded border border-border px-2 py-1 text-xs hover:bg-muted"
                          @click=${() => {
                            liveLogLines = [];
                            void loadLogs();
                            paint();
                          }}
                        >
                          Clear
                        </button>
                      </div>
                    </div>
                    <pre
                      class="max-h-[420px] overflow-auto whitespace-pre-wrap rounded-md bg-muted p-3 font-mono text-xs"
                    >${renderedLogs}</pre>
                  </div>
                </div>
              `
            : null}
          ${menu
            ? html`
                <div
                  class="fixed z-50 min-w-[180px] rounded-md border border-border bg-card py-1 text-sm shadow-lg"
                  style=${`left:${menu.x}px;top:${menu.y}px`}
                  role="menu"
                  @click=${(e: Event) => e.stopPropagation()}
                >
                  ${(["start", "stop", "restart"] as const).map(
                    (action) => html`
                      <button
                        type="button"
                        class="block w-full px-3 py-1.5 text-left hover:bg-muted"
                        @click=${() => void runLifecycle(action, menu!.uuid)}
                      >
                        ${action} (runtime control stub)
                      </button>
                    `,
                  )}
                  <button
                    type="button"
                    class="block w-full px-3 py-1.5 text-left text-destructive hover:bg-muted"
                    @click=${() => {
                      if (
                        window.confirm(
                          "Remove this item from the stub list? This action is not implemented in Docker BAS Lite.",
                        )
                      ) {
                        void runLifecycle("remove", menu!.uuid);
                      }
                      closeMenu();
                    }}
                  >
                    Remove…
                  </button>
                </div>
              `
            : null}
          ${lifecycleErr ? html`<p class="text-sm text-destructive">${lifecycleErr}</p>` : null}
          ${lifecycleOut
            ? html`<pre class="rounded-md bg-muted p-3 text-xs whitespace-pre-wrap">${lifecycleOut}</pre>`
            : null}
        </div>
      `,
      outlet,
    );
  };

  const closeMenu = () => {
    if (menu) {
      menu = null;
      paint();
    }
  };

  const loadMetrics = async () => {
    try {
      metrics = await apiFetch<Metrics>("api/system/metrics");
    } catch {
      metrics = null;
    }
    paint();
  };

  const loadVctl = async () => {
    try {
      vctl = await apiFetch<Vctl>("api/agents/vctl");
    } catch {
      vctl = null;
    }
    paint();
  };

  const loadContainers = async () => {
    try {
      containers = await apiFetch<ContainersResponse>("api/system/containers");
    } catch {
      containers = null;
    }
    paint();
  };

  const loadMessaging = async () => {
    try {
      messaging = await apiFetch<Messaging>("api/system/messaging");
    } catch {
      messaging = null;
    }
    paint();
  };

  const loadLogs = async () => {
    if (!selectedContainer) return;
    try {
      logs = await apiFetch<ContainerLogs>(
        `api/system/container-logs?name=${encodeURIComponent(selectedContainer)}`,
      );
    } catch {
      logs = null;
    }
    paint();
  };

  const selectLogs = (name: string) => {
    liveLogLines = [];
    selectedContainer = name;
    wireSse();
    void loadLogs();
    paint();
  };

  const wireSse = () => {
    try {
      es?.close();
    } catch {
      /* ignore */
    }
    es = null;
    if (!selectedContainer) {
      streamStatus = "idle";
      return;
    }
    streamStatus = "connecting";
    const sseUrl = apiUrl(
      `api/system/container-logs/stream?name=${encodeURIComponent(selectedContainer)}&backlog=120`,
    );
    const source = new EventSource(sseUrl);
    es = source;
    source.onopen = () => {
      streamStatus = "live";
      paint();
    };
    source.onmessage = (evt) => {
      const line = evt.data ?? "";
      if (!line) return;
      liveLogLines = [...liveLogLines, line];
      if (liveLogLines.length > 800) liveLogLines = liveLogLines.slice(liveLogLines.length - 800);
      paint();
    };
    source.addEventListener("error", () => {
      streamStatus = "error";
      paint();
    });
  };

  const containerAction = async (name: string, action: "restart" | "stop" | "start") => {
    await apiFetch("api/system/container-action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, action }),
    });
    await loadContainers();
  };

  const runLifecycle = async (action: string, uuid: string) => {
    lifecycleErr = null;
    lifecycleOut = null;
    closeMenu();
    try {
      const res = await apiFetch<{ status: string; stderr: string; stdout: string; exitCode: number }>(
        "api/agents/lifecycle",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action, uuid }),
        },
      );
      if (res.status !== "ok") lifecycleOut = res.stderr || res.stdout;
      await loadVctl();
    } catch (e) {
      lifecycleErr = e instanceof Error ? e.message : "Lifecycle error";
    }
    paint();
  };

  const boot = async () => {
    loading = true;
    paint();
    await Promise.all([loadMetrics(), loadVctl(), loadContainers(), loadMessaging()]);
    loading = false;
    paint();
  };

  void boot();
  const unsub = subscribeTopics((topic) => {
    if (topic === "system.tick" || topic === "system.metrics.updated") void loadMetrics();
    if (topic === "system.tick") {
      void loadVctl();
      void loadContainers();
      void loadMessaging();
    }
  });
  const iv = window.setInterval(() => void loadMetrics(), 30_000);

  return () => {
    window.clearInterval(iv);
    unsub();
    try {
      es?.close();
    } catch {
      /* ignore */
    }
    render(html``, outlet);
  };
};
