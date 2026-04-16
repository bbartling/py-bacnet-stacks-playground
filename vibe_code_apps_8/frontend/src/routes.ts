export type RouteId =
  | "overview"
  | "live-points"
  | "driver"
  | "system"
  | "faults"
  | "alarms"
  | "schedule"
  | "docs";

export const ROUTE_ORDER: RouteId[] = [
  "overview",
  "live-points",
  "driver",
  "faults",
  "alarms",
  "schedule",
  "system",
  "docs",
];

export const ROUTE_META: Record<
  RouteId,
  { segment: string; label: string; end?: boolean }
> = {
  overview: { segment: "", label: "Overview", end: true },
  "live-points": { segment: "live-points", label: "Live points" },
  driver: { segment: "driver", label: "Driver configs" },
  faults: { segment: "faults", label: "Faults" },
  alarms: { segment: "alarms", label: "Alarms" },
  schedule: { segment: "schedule", label: "Occupancy" },
  system: { segment: "system", label: "System" },
  docs: { segment: "docs", label: "Deployment notes" },
};

export function routeFromPathname(): RouteId {
  const raw = (import.meta.env.BASE_URL ?? "/").replace(/\/+$/, "") || "";
  const path = window.location.pathname;
  if (!path.startsWith(raw === "" ? "/" : raw)) return "overview";
  const rest = path.slice(raw.length).replace(/^\/+/, "");
  const seg = rest.split("/")[0] ?? "";
  if (!seg || seg === "index.html") return "overview";
  for (const id of ROUTE_ORDER) {
    const s = ROUTE_META[id].segment;
    if (s === seg) return id;
  }
  return "overview";
}

export function pathForRoute(id: RouteId): string {
  const base = (import.meta.env.BASE_URL ?? "/").replace(/\/?$/, "/");
  const seg = ROUTE_META[id].segment;
  return seg ? `${base}${seg}` : base;
}
