import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { apiFetch } from "@/lib/bas-fetch";

type PointRow = {
  id: string;
  deviceId: string;
  label: string;
  name: string;
  units: string;
  value: unknown;
  lastUpdated: string | null;
  adjustable: boolean;
  alarmState: string;
};

export function BasLivePointsPage() {
  const qc = useQueryClient();
  const [edit, setEdit] = useState<{ pointId: string; value: string } | null>(null);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [filter, setFilter] = useState("");

  const points = useQuery({
    queryKey: ["bas-points"],
    queryFn: () => apiFetch<{ items: PointRow[] }>("api/points"),
    staleTime: 15_000,
  });

  const write = useMutation({
    mutationFn: async (body: { pointId: string; value: number | string }) =>
      apiFetch<{ status: string; message?: string }>("api/setpoints/write", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["bas-points"] });
      setEdit(null);
    },
  });

  const byDevice = useMemo(() => {
    const m = new Map<string, PointRow[]>();
    for (const p of points.data?.items ?? []) {
      if (filter.trim()) {
        const q = filter.trim().toLowerCase();
        const hay = `${p.deviceId} ${p.label} ${p.name}`.toLowerCase();
        if (!hay.includes(q)) continue;
      }
      const list = m.get(p.deviceId) ?? [];
      list.push(p);
      m.set(p.deviceId, list);
    }
    return m;
  }, [points.data, filter]);

  useEffect(() => {
    const next: Record<string, boolean> = {};
    for (const [d] of byDevice.entries()) next[d] = expanded[d] ?? true;
    setExpanded(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [points.data, filter]);

  if (points.isLoading) return <Skeleton className="h-96 w-full rounded-xl" />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Live points</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Point tree by device with live values and writable setpoints using BACnet JSON-RPC.
        </p>
        <input
          className="mt-3 w-full max-w-md rounded border border-border bg-background px-2 py-1 text-sm"
          placeholder="Filter device/point..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
      </div>

      {Array.from(byDevice.entries()).map(([deviceId, rows]) => (
        <Card key={deviceId}>
          <CardContent className="pt-6">
            <button
              type="button"
              className="mb-3 inline-flex items-center gap-2 text-left text-sm font-semibold"
              onClick={() => setExpanded((p) => ({ ...p, [deviceId]: !p[deviceId] }))}
            >
              <span>{expanded[deviceId] ? "▾" : "▸"}</span>
              <span>{deviceId}</span>
              <span className="text-xs text-muted-foreground">({rows.length} points)</span>
            </button>
            {expanded[deviceId] ? (
              <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Point</TableHead>
                  <TableHead>Value</TableHead>
                  <TableHead>Updated</TableHead>
                  <TableHead>Alarm</TableHead>
                  <TableHead className="text-right">Write</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell>
                      <div className="font-medium">{p.label}</div>
                      <div className="text-xs text-muted-foreground font-mono">{p.name}</div>
                    </TableCell>
                    <TableCell className="font-mono text-sm">
                      {String(p.value ?? "—")} {p.units}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">{p.lastUpdated ?? "—"}</TableCell>
                    <TableCell className="text-xs">{p.alarmState}</TableCell>
                    <TableCell className="text-right">
                      {p.adjustable ? (
                        edit?.pointId === p.id ? (
                          <span className="inline-flex gap-1">
                            <input
                              className="w-24 rounded border border-border bg-background px-2 py-1 text-xs"
                              value={edit.value}
                              onChange={(e) => setEdit({ pointId: p.id, value: e.target.value })}
                            />
                            <button
                              type="button"
                              className="rounded bg-primary px-2 py-1 text-xs text-primary-foreground"
                              onClick={() =>
                                write.mutate({
                                  pointId: p.id,
                                  value: Number(edit.value),
                                })
                              }
                            >
                              Send
                            </button>
                          </span>
                        ) : (
                          <button
                            type="button"
                            className="text-xs text-primary hover:underline"
                            onClick={() =>
                              setEdit({ pointId: p.id, value: String(p.value ?? "") })
                            }
                          >
                            Edit
                          </button>
                        )
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
              </Table>
            ) : null}
          </CardContent>
        </Card>
      ))}

      {write.isError ? (
        <p className="text-sm text-destructive">{(write.error as Error).message}</p>
      ) : null}
    </div>
  );
}
