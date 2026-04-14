import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";
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
import { apiFetch, apiUrl } from "@/lib/bas-fetch";

type Metrics = {
  timestamp: string;
  cpuPercent: number | null;
  loadavg: { load1: number | null; load5: number | null; load15: number | null };
  memory: { memTotalBytes: number | null; memAvailableBytes: number | null; memUsedBytes: number | null };
  diskRoot: { totalBytes: number | null; usedBytes: number | null; freeBytes: number | null; usedPercent: number | null };
  hostname: string | null;
};

type Vctl = {
  exitCode: number;
  stdout: string;
  stderr: string;
  agents: { uuid: string; summary: string }[];
};

function fmtGb(bytes: number | null | undefined): string {
  if (bytes == null) return "—";
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}

export function BasSystemPage() {
  const qc = useQueryClient();
  const [menu, setMenu] = useState<{ x: number; y: number; uuid: string; summary: string } | null>(null);

  const metrics = useQuery({
    queryKey: ["bas-metrics"],
    queryFn: () => apiFetch<Metrics>("api/system/metrics"),
    refetchInterval: 5000,
  });

  const vctl = useQuery({
    queryKey: ["bas-vctl"],
    queryFn: () => apiFetch<Vctl>("api/agents/vctl"),
    refetchInterval: 8000,
  });

  const lifecycle = useMutation({
    mutationFn: async (body: { action: string; tag?: string; uuid?: string }) => {
      return apiFetch<{ status: string; stderr: string; stdout: string; exitCode: number }>(
        "api/agents/lifecycle",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
      );
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["bas-vctl"] });
    },
  });

  const closeMenu = useCallback(() => setMenu(null), []);

  return (
    <div className="space-y-6" onClick={closeMenu}>
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">System</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Raspberry Pi and container resources from the App 8 web agent. Service status is summarized here; deeper checks
          still belong to <code className="rounded bg-muted px-1">docker compose ps</code> and logs on the host.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardContent className="pt-6 space-y-3 text-sm">
            <p className="text-xs font-medium uppercase text-muted-foreground">Host</p>
            {metrics.isLoading ? (
              <Skeleton className="h-24 w-full" />
            ) : (
              <>
                <p className="font-mono text-base">{metrics.data?.hostname ?? "—"}</p>
                <p>
                  CPU:{" "}
                  <span className="font-medium">
                    {metrics.data?.cpuPercent != null ? `${metrics.data.cpuPercent}%` : "n/a"}
                  </span>
                </p>
                <p className="text-muted-foreground">
                  Load (1/5/15):{" "}
                  {metrics.data?.loadavg.load1 ?? "—"} / {metrics.data?.loadavg.load5 ?? "—"} /{" "}
                  {metrics.data?.loadavg.load15 ?? "—"}
                </p>
                <p>
                  RAM used: {fmtGb(metrics.data?.memory.memUsedBytes)} /{" "}
                  {fmtGb(metrics.data?.memory.memTotalBytes)}
                </p>
                <p>
                  Disk (/): {metrics.data?.diskRoot.usedPercent ?? "—"}% used · free{" "}
                  {fmtGb(metrics.data?.diskRoot.freeBytes)}
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardContent className="pt-6">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs font-medium uppercase text-muted-foreground">Container and edge status</p>
              <button
                type="button"
                className="rounded border border-border px-2 py-1 text-xs hover:bg-muted"
                onClick={() => qc.invalidateQueries({ queryKey: ["bas-vctl"] })}
              >
                Refresh
              </button>
            </div>
            {vctl.isLoading ? (
              <Skeleton className="h-48 w-full" />
            ) : (
              <div className="max-h-[420px] overflow-auto rounded-md border border-border/60">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[280px]">Identifier</TableHead>
                      <TableHead>Summary</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {vctl.data?.agents.map((a) => (
                      <TableRow
                        key={a.uuid}
                        className="cursor-context-menu"
                        onContextMenu={(e) => {
                          e.preventDefault();
                          setMenu({ x: e.clientX, y: e.clientY, uuid: a.uuid, summary: a.summary });
                        }}
                      >
                        <TableCell className="font-mono text-xs">{a.uuid}</TableCell>
                        <TableCell className="text-xs">{a.summary}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
                {vctl.data?.stderr ? (
                  <pre className="border-t border-border/60 bg-destructive/10 p-2 text-xs whitespace-pre-wrap">
                    {vctl.data.stderr}
                  </pre>
                ) : null}
              </div>
            )}
            <p className="mt-2 text-xs text-muted-foreground">
              Status endpoint: <code className="rounded bg-muted px-1">{apiUrl("api/agents/vctl")}</code>
            </p>
          </CardContent>
        </Card>
      </div>

      {menu ? (
        <div
          className="fixed z-50 min-w-[180px] rounded-md border border-border bg-card py-1 text-sm shadow-lg"
          style={{ left: menu.x, top: menu.y }}
          role="menu"
        >
              {(["start", "stop", "restart"] as const).map((action) => (
            <button
              key={action}
              type="button"
              className="block w-full px-3 py-1.5 text-left hover:bg-muted"
              onClick={() => {
                lifecycle.mutate({ action, uuid: menu.uuid });
                closeMenu();
              }}
            >
              {action}
            </button>
          ))}
          <button
            type="button"
            className="block w-full px-3 py-1.5 text-left text-destructive hover:bg-muted"
            onClick={() => {
              if (
                window.confirm(
                  "Remove this agent from VOLTTRON?",
                )
              ) {
                lifecycle.mutate({ action: "remove", uuid: menu.uuid });
              }
              closeMenu();
            }}
          >
            Remove…
          </button>
        </div>
      ) : null}

      {lifecycle.isError ? (
        <p className="text-sm text-destructive">
          {(lifecycle.error as Error)?.message ?? "Lifecycle error"}
        </p>
      ) : null}
      {lifecycle.data && lifecycle.data.status !== "ok" ? (
        <pre className="rounded-md bg-muted p-3 text-xs whitespace-pre-wrap">
          {lifecycle.data.stderr || lifecycle.data.stdout}
        </pre>
      ) : null}
    </div>
  );
}
