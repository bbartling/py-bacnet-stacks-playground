import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { apiFetch } from "@/lib/bas-fetch";

type TrendResp = {
  pointId: string;
  label: string;
  units: string;
  items: { ts: string; value: number | string }[];
};

type HealthLite = { defaultTrendPointId?: string };

export function BasTrendsPage() {
  const health = useQuery({
    queryKey: ["bas-health"],
    queryFn: () => apiFetch<HealthLite>("api/health"),
  });
  const [manualPointId, setManualPointId] = useState<string | null>(null);
  const pointId = manualPointId ?? health.data?.defaultTrendPointId ?? "";

  const trend = useQuery({
    queryKey: ["bas-trend", pointId],
    queryFn: () => apiFetch<TrendResp>(`api/trends?pointId=${encodeURIComponent(pointId)}`),
    enabled: Boolean(pointId),
    refetchInterval: 15_000,
  });

  const chartData = useMemo(
    () =>
      (trend.data?.items ?? []).map((r) => ({
        t: new Date(r.ts).getTime(),
        v: typeof r.value === "number" ? r.value : Number(r.value),
      })),
    [trend.data],
  );

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Trends</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          In-memory trend buffers from the BAS Lite agent (same behavior as App 7).
        </p>
      </div>
      <Card>
        <CardContent className="space-y-3 pt-6">
          <label className="text-sm">
            Point ID{" "}
            <input
              className="ml-2 w-72 rounded border border-border bg-background px-2 py-1 font-mono text-xs"
              value={pointId}
              onChange={(e) => setManualPointId(e.target.value)}
            />
          </label>
          {trend.isLoading ? (
            <Skeleton className="h-72 w-full" />
          ) : (
            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                  <XAxis
                    dataKey="t"
                    type="number"
                    domain={["dataMin", "dataMax"]}
                    tickFormatter={(v) => new Date(v).toLocaleTimeString()}
                    fontSize={11}
                  />
                  <YAxis fontSize={11} domain={["auto", "auto"]} />
                  <Tooltip
                    labelFormatter={(v) => new Date(Number(v)).toLocaleString()}
                    formatter={(v) => [`${v ?? ""}`, trend.data?.label ?? "value"]}
                  />
                  <Line type="monotone" dataKey="v" stroke="hsl(215, 60%, 42%)" dot={false} strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
          <p className="text-xs text-muted-foreground">
            Units: {trend.data?.units ?? "—"} · Samples: {chartData.length}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
