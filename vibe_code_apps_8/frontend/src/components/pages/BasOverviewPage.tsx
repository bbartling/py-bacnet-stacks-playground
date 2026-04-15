import { useQuery } from "@tanstack/react-query";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { apiFetch } from "@/lib/bas-fetch";
import { Link } from "react-router-dom";
import { useBasWebSocket } from "@/hooks/use-bas-websocket";

type Health = {
  status: string;
  appTitle: string;
  siteName: string;
  routePrefix: string;
  trendPolicy: { intervalMinutes: number; retentionDays: number; maxSamplesPerPoint: number };
};

type Device = {
  id: string;
  displayName: string;
  status: string;
  lastSeen: string | null;
  pointCount: number;
};

export function BasOverviewPage() {
  useBasWebSocket();
  const health = useQuery({
    queryKey: ["bas-health"],
    queryFn: () => apiFetch<Health>("api/health"),
  });
  const devices = useQuery({
    queryKey: ["bas-devices"],
    queryFn: () => apiFetch<{ items: Device[] }>("api/devices"),
    staleTime: 15_000,
  });
  const points = useQuery({
    queryKey: ["bas-points"],
    queryFn: () => apiFetch<{ items: { deviceId: string; label: string; value: unknown; units: string }[] }>("api/points"),
    staleTime: 15_000,
  });

  if (health.isLoading) return <Skeleton className="h-40 w-full rounded-xl" />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Overview</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          BAS / BMS Lite on Docker + easy-aso — asyncio supervisor, operator dashboard, driver file
          store, and weekly occupancy schedules.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardContent className="pt-6">
            <p className="text-xs font-medium uppercase text-muted-foreground">Site</p>
            <p className="mt-1 text-lg font-semibold">{health.data?.siteName}</p>
            <p className="mt-2 text-xs text-muted-foreground">
              Trends: {health.data?.trendPolicy.intervalMinutes} min samples ·{" "}
              {health.data?.trendPolicy.retentionDays} day target retention
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-xs font-medium uppercase text-muted-foreground">Shortcuts</p>
            <ul className="mt-2 space-y-1.5 text-sm">
              <li>
                <Link className="text-primary hover:underline" to="/live-points">
                  Live points &amp; setpoints
                </Link>
              </li>
              <li>
                <Link className="text-primary hover:underline" to="/driver">
                  Driver config files
                </Link>
              </li>
              <li>
                <Link className="text-primary hover:underline" to="/system">
                  Pi resources &amp; containers
                </Link>
              </li>
              <li>
                <Link className="text-primary hover:underline" to="/schedule">
                  Weekly occupancy schedule
                </Link>
              </li>
            </ul>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-xs font-medium uppercase text-muted-foreground">Equipment</p>
            {devices.isLoading ? (
              <Skeleton className="mt-2 h-20 w-full" />
            ) : (
              <ul className="mt-2 space-y-2 text-sm">
                {devices.data?.items.map((d) => (
                  <li key={d.id} className="flex justify-between gap-2">
                    <span className="font-medium">{d.displayName}</span>
                    <span className="text-muted-foreground">
                      {d.status} · {d.pointCount} pts
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
      <Card>
        <CardContent className="pt-6">
          <p className="text-xs font-medium uppercase text-muted-foreground">Points by equipment</p>
          <div className="mt-3 space-y-3">
            {(devices.data?.items ?? []).map((d) => {
              const rows = (points.data?.items ?? []).filter((p) => p.deviceId === d.id).slice(0, 5);
              return (
                <div key={d.id} className="rounded-md border border-border/60 p-3">
                  <p className="text-sm font-medium">{d.displayName}</p>
                  <ul className="mt-1 space-y-1 text-xs text-muted-foreground">
                    {rows.map((p, idx) => (
                      <li key={`${d.id}-${idx}`}>
                        {p.label}: {String(p.value ?? "—")} {p.units}
                      </li>
                    ))}
                    {rows.length === 0 ? <li>No points available.</li> : null}
                  </ul>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
