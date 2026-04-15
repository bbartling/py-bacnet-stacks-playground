import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState } from "react";
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

type ContainerRow = {
  id: string;
  name: string;
  service: string;
  status: string;
  image: string;
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

export function BasSystemPage() {
  const qc = useQueryClient();
  const [menu, setMenu] = useState<{ x: number; y: number; uuid: string; summary: string } | null>(null);
  const [selectedContainer, setSelectedContainer] = useState("");
  const [liveLogLines, setLiveLogLines] = useState<string[]>([]);
  const [streamStatus, setStreamStatus] = useState<"idle" | "connecting" | "live" | "error">("idle");

  const metrics = useQuery({
    queryKey: ["bas-metrics"],
    queryFn: () => apiFetch<Metrics>("api/system/metrics"),
    staleTime: 10_000,
    refetchInterval: 30_000,
  });

  const vctl = useQuery({
    queryKey: ["bas-vctl"],
    queryFn: () => apiFetch<Vctl>("api/agents/vctl"),
    staleTime: 15_000,
    refetchInterval: 45_000,
  });

  const containers = useQuery({
    queryKey: ["bas-system-containers"],
    queryFn: () => apiFetch<ContainersResponse>("api/system/containers"),
    staleTime: 20_000,
    refetchInterval: 60_000,
  });

  const messaging = useQuery({
    queryKey: ["bas-messaging-status"],
    queryFn: () => apiFetch<Messaging>("api/system/messaging"),
    staleTime: 20_000,
    refetchInterval: 60_000,
  });

  const logs = useQuery({
    queryKey: ["bas-container-logs", selectedContainer],
    queryFn: () => apiFetch<ContainerLogs>(`api/system/container-logs?name=${encodeURIComponent(selectedContainer)}`),
    enabled: Boolean(selectedContainer),
    staleTime: 20_000,
    refetchInterval: 60_000,
  });

  useEffect(() => {
    if (!selectedContainer) {
      setLiveLogLines([]);
      setStreamStatus("idle");
      return;
    }
    setStreamStatus("connecting");
    const sseUrl = apiUrl(`api/system/container-logs/stream?name=${encodeURIComponent(selectedContainer)}&backlog=120`);
    const es = new EventSource(sseUrl);
    es.onopen = () => setStreamStatus("live");
    es.onmessage = (evt) => {
      const line = evt.data ?? "";
      if (!line) return;
      setLiveLogLines((prev) => {
        const next = [...prev, line];
        return next.length > 800 ? next.slice(next.length - 800) : next;
      });
    };
    es.addEventListener("error", () => setStreamStatus("error"));
    return () => {
      es.close();
      setStreamStatus("idle");
    };
  }, [selectedContainer]);

  const renderedLogs = useMemo(() => {
    if (liveLogLines.length > 0) return liveLogLines.join("\n");
    return logs.data?.logs || logs.data?.message || "No logs.";
  }, [liveLogLines, logs.data]);

  const containerAction = useMutation({
    mutationFn: async (body: { name: string; action: "restart" | "stop" | "start" }) =>
      apiFetch<{ ok: boolean; action?: string; name?: string; status?: string }>("api/system/container-action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["bas-system-containers"] });
    },
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
          Raspberry Pi resources from the API container. Container status is summarized here, and deeper service checks
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

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardContent className="pt-6 space-y-3 text-sm">
            <p className="text-xs font-medium uppercase text-muted-foreground">BACnet + MQTT</p>
            {messaging.isLoading ? (
              <Skeleton className="h-20 w-full" />
            ) : (
              <>
                <p>
                  BACnet online:{" "}
                  <span className={messaging.data?.bacnetOnline ? "font-medium text-emerald-600" : "font-medium text-destructive"}>
                    {messaging.data?.bacnetOnline ? "yes" : "no"}
                  </span>
                </p>
                <p className="font-mono text-xs text-muted-foreground">{messaging.data?.bacnetRpcUrl}</p>
                <p>
                  MQTT bridge: <span className="font-medium">{messaging.data?.mqttBridgeOnline ? "online" : "planned / offline"}</span>
                </p>
                <p className="text-xs text-muted-foreground">{messaging.data?.note}</p>
              </>
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardContent className="pt-6">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs font-medium uppercase text-muted-foreground">Docker stack (compose project)</p>
              <button
                type="button"
                className="rounded border border-border px-2 py-1 text-xs hover:bg-muted"
                onClick={() => qc.invalidateQueries({ queryKey: ["bas-system-containers"] })}
              >
                Refresh
              </button>
            </div>
            <p className="mb-2 text-xs text-muted-foreground">
              Includes optional easy-aso sidecars (for example the OAT share agent). Use restart/stop/start for quick
              operator cycles; logs still tail below.
            </p>
            {containers.isLoading ? (
              <Skeleton className="h-48 w-full" />
            ) : !containers.data?.dockerAvailable ? (
              <p className="text-sm text-muted-foreground">
                Docker socket unavailable in API container. Endpoint:{" "}
                <code className="rounded bg-muted px-1">{apiUrl("api/system/containers")}</code>
              </p>
            ) : (
              <div className="max-h-[280px] overflow-auto rounded-md border border-border/60">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Service</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {containers.data.items.map((c) => (
                      <TableRow key={c.id}>
                        <TableCell className="font-mono text-xs">{c.name}</TableCell>
                        <TableCell className="text-xs">{c.service || "—"}</TableCell>
                        <TableCell className="text-xs">{c.status}</TableCell>
                        <TableCell className="text-right space-x-2 whitespace-nowrap">
                          <button
                            type="button"
                            className="text-xs text-primary hover:underline"
                            onClick={() => setSelectedContainer(c.name)}
                          >
                            logs
                          </button>
                          <button
                            type="button"
                            className="text-xs text-muted-foreground hover:underline disabled:opacity-40"
                            disabled={containerAction.isPending}
                            onClick={() => containerAction.mutate({ name: c.name, action: "restart" })}
                          >
                            restart
                          </button>
                          <button
                            type="button"
                            className="text-xs text-muted-foreground hover:underline disabled:opacity-40"
                            disabled={containerAction.isPending}
                            onClick={() => containerAction.mutate({ name: c.name, action: "stop" })}
                          >
                            stop
                          </button>
                          <button
                            type="button"
                            className="text-xs text-muted-foreground hover:underline disabled:opacity-40"
                            disabled={containerAction.isPending}
                            onClick={() => containerAction.mutate({ name: c.name, action: "start" })}
                          >
                            start
                          </button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {selectedContainer ? (
        <Card>
          <CardContent className="pt-6">
            <div className="mb-2 flex items-center justify-between gap-2">
              <p className="text-xs font-medium uppercase text-muted-foreground">
                Container logs: <span className="normal-case font-mono">{selectedContainer}</span>
              </p>
              <div className="flex items-center gap-2">
                <span
                  className={`text-xs ${
                    streamStatus === "live"
                      ? "text-emerald-600"
                      : streamStatus === "error"
                        ? "text-destructive"
                        : "text-muted-foreground"
                  }`}
                >
                  {streamStatus === "live" ? "streaming live" : streamStatus === "connecting" ? "connecting…" : streamStatus}
                </span>
                <button
                  type="button"
                  className="rounded border border-border px-2 py-1 text-xs hover:bg-muted"
                  onClick={() => {
                    setLiveLogLines([]);
                    qc.invalidateQueries({ queryKey: ["bas-container-logs", selectedContainer] });
                  }}
                >
                  Clear
                </button>
              </div>
            </div>
            {logs.isLoading ? (
              <Skeleton className="h-56 w-full" />
            ) : (
              <pre className="max-h-[420px] overflow-auto rounded-md bg-muted p-3 font-mono text-xs whitespace-pre-wrap">
                {renderedLogs}
              </pre>
            )}
          </CardContent>
        </Card>
      ) : null}

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
              {action} (runtime control stub)
            </button>
          ))}
          <button
            type="button"
            className="block w-full px-3 py-1.5 text-left text-destructive hover:bg-muted"
            onClick={() => {
              if (
                window.confirm(
                  "Remove this item from the stub list? This action is not implemented in Docker BAS Lite.",
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
