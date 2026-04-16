import { html, render } from "lit-html";
import { apiFetch } from "./api";
import { pathForRoute, ROUTE_META, ROUTE_ORDER, type RouteId } from "./routes";
import { isDarkMode, readStoredTheme, setStoredTheme, type ThemePref } from "./theme";
import { subscribeTopics } from "./topics";

type Health = {
  status: string;
  appTitle: string;
  siteName: string;
  lastPublishAt: string | null;
  counts: { devices: number; points: number; activeAlarms: number };
};

type SystemTime = { weekday: string; localDate: string; localTime: string };

export type ShellHandles = {
  outlet: HTMLElement;
  setRoute: (r: RouteId) => void;
  dispose: () => void;
};

export function mountShell(
  root: HTMLElement,
  opts: { navigate: (r: RouteId) => void; getRoute: () => RouteId },
): ShellHandles {
  root.replaceChildren();

  const row = document.createElement("div");
  row.className = "flex h-screen overflow-hidden bg-background";

  const sidebarHost = document.createElement("aside");
  sidebarHost.className = "flex w-60 shrink-0 flex-col border-r border-border/60 bg-card/50";

  const col = document.createElement("div");
  col.className = "flex flex-1 flex-col overflow-hidden";

  const topHost = document.createElement("header");
  topHost.className =
    "flex h-14 shrink-0 items-center justify-between gap-4 border-b border-border/60 bg-card/80 px-6 backdrop-blur-lg";

  const healthHost = document.createElement("div");

  const main = document.createElement("main");
  main.className = "flex-1 overflow-y-auto";
  const outlet = document.createElement("div");
  outlet.className = "mx-auto max-w-7xl px-6 py-8";
  main.append(outlet);

  col.append(topHost, healthHost, main);
  row.append(sidebarHost, col);
  root.append(row);

  let timeData: SystemTime | null = null;
  let healthData: Health | null = null;
  const paintSidebar = (active: RouteId) => {
    render(
      html`
        <div class="flex h-full min-h-0 flex-col">
          <div class="flex items-center gap-2.5 border-border/60 px-5 py-4">
            <span class="text-lg font-semibold tracking-tight text-foreground">BAS Lite</span>
            <span
              class="rounded-md border border-border px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground"
              >Docker</span
            >
          </div>
          <nav class="min-h-0 flex-1 space-y-0.5 overflow-y-auto px-3 py-2">
            ${ROUTE_ORDER.map((id) => {
              const meta = ROUTE_META[id];
              const href = pathForRoute(id);
              const isActive = active === id;
              return html`
                <a
                  href=${href}
                  class=${isActive
                    ? "flex items-center gap-3 rounded-lg bg-muted/70 px-3 py-2 text-sm font-medium text-foreground transition-colors duration-150"
                    : "flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-muted-foreground transition-colors duration-150 hover:bg-muted/40 hover:text-foreground"}
                  @click=${(e: MouseEvent) => {
                    e.preventDefault();
                    opts.navigate(id);
                  }}
                >
                  <span class="w-4 shrink-0 text-center text-xs">${navGlyph(id)}</span>
                  <span>${meta.label}</span>
                </a>
              `;
            })}
          </nav>
          <div class="border-t border-border/60 px-5 py-3">
            <div class="flex items-center rounded-lg bg-muted/60 p-1">
              ${(["light", "dark"] as const).map((pref) => {
                const stored = readStoredTheme();
                const activePref: ThemePref =
                  stored === "light" || stored === "dark" ? stored : isDarkMode() ? "dark" : "light";
                const isSel = activePref === pref;
                return html`
                  <button
                    type="button"
                    class=${isSel
                      ? "flex flex-1 items-center justify-center rounded-md bg-background p-1.5 text-foreground shadow-sm transition-colors duration-150"
                      : "flex flex-1 items-center justify-center rounded-md p-1.5 text-muted-foreground transition-colors duration-150 hover:text-foreground"}
                    aria-label=${pref === "light" ? "Light theme" : "Dark theme"}
                    title=${pref === "light" ? "Light" : "Dark"}
                    @click=${() => {
                      setStoredTheme(pref);
                      paintTop();
                      paintSidebar(opts.getRoute());
                    }}
                  >
                    <span class="text-sm">${pref === "light" ? "☀" : "☾"}</span>
                  </button>
                `;
              })}
            </div>
          </div>
        </div>
      `,
      sidebarHost,
    );
  };

  const paintTop = () => {
    const dark = isDarkMode();
    render(
      html`
        <div class="min-w-0">
          <p class="truncate text-sm font-medium text-foreground">BAS Lite: Open, Free, and Built for Makers</p>
          <p class="truncate text-xs text-muted-foreground">
            Discover fast, automate freely, and keep your building data in your hands
          </p>
        </div>
        <div class="flex items-center gap-2">
          <span class="text-xs text-muted-foreground">
            ${timeData
              ? `${timeData.weekday} ${timeData.localDate} ${timeData.localTime}`
              : "Host time…"}
          </span>
          <span
            class="cursor-help text-xs text-muted-foreground"
            title="Vanilla TypeScript + lit-html SPA behind Caddy with websocket + SSE updates."
            >Help</span
          >
          <button
            type="button"
            class="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            aria-label=${dark ? "Switch to light mode" : "Switch to dark mode"}
            @click=${() => {
              setStoredTheme(dark ? "light" : "dark");
              paintTop();
              paintSidebar(opts.getRoute());
            }}
          >
            <span class="text-base">${dark ? "☀" : "☾"}</span>
          </button>
        </div>
      `,
      topHost,
    );
  };

  const paintHealth = () => {
    if (!healthData) {
      render(
        html`<div class="border-b border-border/60 bg-muted/30 px-6 py-1.5 text-xs text-muted-foreground">
          Loading platform health…
        </div>`,
        healthHost,
      );
      return;
    }
    const ok = healthData.status === "ok";
    render(
      html`
        <div
          class="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-border/60 bg-muted/30 px-6 py-1.5 text-xs text-muted-foreground"
        >
          <span class="inline-flex items-center gap-1.5">
            <span class="h-2 w-2 rounded-full ${ok ? "bg-emerald-500" : "bg-destructive"}" aria-hidden="true"></span>
            <span class="font-medium text-foreground">${healthData.appTitle}</span>
            <span>· ${healthData.siteName}</span>
          </span>
          <span>
            Last BACnet publish:
            <span class="font-mono text-foreground">${healthData.lastPublishAt ?? "—"}</span>
          </span>
          <span>
            Devices ${healthData.counts.devices} · Points ${healthData.counts.points} · Active alarms
            ${healthData.counts.activeAlarms}
          </span>
        </div>
      `,
      healthHost,
    );
  };

  const fetchTime = async () => {
    try {
      timeData = await apiFetch<SystemTime>("api/system/time");
    } catch {
      timeData = null;
    }
    paintTop();
  };

  const fetchHealth = async () => {
    try {
      healthData = await apiFetch<Health>("api/health");
    } catch {
      healthData = null;
    }
    paintHealth();
  };

  const unsub = subscribeTopics((topic) => {
    if (topic === "points.updated" || topic === "alarms.updated" || topic === "system.tick") {
      void fetchHealth();
    }
    if (topic === "system.tick") void fetchTime();
  });

  const tHealth = window.setInterval(() => {
    if (!globalPollPaused) void fetchHealth();
  }, 20_000);
  const tTime = window.setInterval(() => {
    if (!globalPollPaused) void fetchTime();
  }, 15_000);

  void fetchTime();
  void fetchHealth();
  paintTop();
  paintSidebar(opts.getRoute());

  return {
    outlet,
    setRoute: (r: RouteId) => {
      paintSidebar(r);
    },
    dispose: () => {
      window.clearInterval(tHealth);
      window.clearInterval(tTime);
      unsub();
    },
  };
}

function navGlyph(id: RouteId): string {
  switch (id) {
    case "overview":
      return "▣";
    case "live-points":
      return "◎";
    case "driver":
      return "⧉";
    case "faults":
      return "⚠";
    case "alarms":
      return "⚡";
    case "schedule":
      return "⏱";
    case "system":
      return "⌁";
    case "docs":
      return "📄";
    default:
      return "·";
  }
}

let globalPollPaused = false;

/** When the overview setpoint dock has focus, pause shell polling (mirrors React dockFocus). */
export function setGlobalPollDockFocus(v: boolean): void {
  globalPollPaused = v;
}

export function getGlobalPollPaused(): boolean {
  return globalPollPaused;
}
