import { useQuery } from "@tanstack/react-query";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { vtFetch } from "@/lib/volttron-fetch";
import { Link } from "react-router-dom";

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
  const health = useQuery({
    queryKey: ["bas-health"],
    queryFn: () => vtFetch<Health>("api/health"),
  });
  const devices = useQuery({
    queryKey: ["bas-devices"],
    queryFn: () => vtFetch<{ items: Device[] }>("api/devices"),
    refetchInterval: 10_000,
  });

  if (health.isLoading) return <Skeleton className="h-40 w-full rounded-xl" />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Overview</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          BAS / BMS Lite on Docker + easy-aso — asyncio supervisor, operator dashboard, driver file
          store, and weekly occupancy schedules (no VOLTTRON).
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
                  Platform Driver configs
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
    </div>
  );
}
