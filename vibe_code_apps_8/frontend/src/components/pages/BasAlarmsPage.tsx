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
import { useBasWebSocket } from "@/hooks/use-bas-websocket";

type AlarmEvent = {
  id: string;
  severity: string;
  state: string;
  message: string;
  triggeredAt: string;
  deviceId: string;
  pointId: string;
};

type AlarmDefinition = {
  id?: string;
  pointId?: string;
  enabled?: boolean;
  severity?: string;
  threshold?: number;
  comparison?: string;
  [k: string]: unknown;
};

type NotificationsCfg = {
  smtp: {
    enabled?: boolean;
    host?: string;
    port?: number;
    username?: string;
    password?: string;
    from?: string;
    to?: string[];
    starttls?: boolean;
    ssl?: boolean;
    timeoutSec?: number;
  };
};

function prettyJson(v: unknown): string {
  return JSON.stringify(v, null, 2);
}

export function BasAlarmsPage() {
  useBasWebSocket();
  const qc = useQueryClient();
  const [draft, setDraft] = useState<string>("");
  const [draftTouched, setDraftTouched] = useState(false);
  const [smtpDraft, setSmtpDraft] = useState<string>("");
  const [smtpTouched, setSmtpTouched] = useState(false);
  const [restorePayload, setRestorePayload] = useState("");

  const events = useQuery({
    queryKey: ["bas-alarm-events"],
    queryFn: () => apiFetch<{ items: AlarmEvent[] }>("api/alarms/events"),
    staleTime: 15_000,
  });

  const definitions = useQuery({
    queryKey: ["bas-alarm-definitions"],
    queryFn: () => apiFetch<{ items: AlarmDefinition[] }>("api/alarms/definitions"),
  });

  const notifications = useQuery({
    queryKey: ["bas-notifications-config"],
    queryFn: () => apiFetch<NotificationsCfg>("api/notifications/config"),
  });

  const saveDefinitions = useMutation({
    mutationFn: async (items: AlarmDefinition[]) =>
      apiFetch<{ status: string; count: number }>("api/alarms/definitions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ items }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["bas-alarm-definitions"] });
    },
  });

  const ackEvent = useMutation({
    mutationFn: async (eventId: string) =>
      apiFetch<{ status: string }>("api/alarms/ack", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ eventId }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["bas-alarm-events"] });
    },
  });

  const saveNotifications = useMutation({
    mutationFn: async (cfg: NotificationsCfg) =>
      apiFetch<{ status: string }>("api/notifications/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cfg),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["bas-notifications-config"] }),
  });

  const testEmail = useMutation({
    mutationFn: async () =>
      apiFetch<{ ok: boolean; message: string }>("api/notifications/test-email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      }),
  });

  const exportBackup = useMutation({
    mutationFn: async () => apiFetch<{ status: string; payload: unknown }>("api/backup/export"),
    onSuccess: (d) => {
      setRestorePayload(prettyJson(d.payload));
    },
  });

  const importBackup = useMutation({
    mutationFn: async (payload: unknown) =>
      apiFetch<{ status: string }>("api/backup/restore", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ payload }),
      }),
  });

  const tableItems = useMemo(() => events.data?.items ?? [], [events.data]);
  const loadedDraft = useMemo(() => prettyJson(definitions.data?.items ?? []), [definitions.data]);

  useEffect(() => {
    if (!draftTouched) setDraft(loadedDraft);
  }, [loadedDraft, draftTouched]);

  const smtpLoaded = useMemo(() => prettyJson(notifications.data ?? { smtp: {} }), [notifications.data]);
  useEffect(() => {
    if (!smtpTouched) setSmtpDraft(smtpLoaded);
  }, [smtpLoaded, smtpTouched]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Alarms</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Supervisory alarm definitions and runtime events. Keep faults analytics separate on the Faults tab.
        </p>
      </div>

      <Card>
        <CardContent className="pt-6">
          <div className="mb-3 flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold">Active alarm events</h2>
          </div>
          {events.isLoading ? (
            <Skeleton className="h-40 w-full" />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Severity</TableHead>
                  <TableHead>State</TableHead>
                  <TableHead>Message</TableHead>
                  <TableHead>Point</TableHead>
                  <TableHead>When</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tableItems.map((e) => (
                  <TableRow key={e.id}>
                    <TableCell className="text-xs font-medium uppercase">{e.severity}</TableCell>
                    <TableCell className="text-xs">{e.state}</TableCell>
                    <TableCell className="text-sm">{e.message}</TableCell>
                    <TableCell className="font-mono text-xs">{e.pointId}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{e.triggeredAt}</TableCell>
                    <TableCell className="text-right">
                      <button
                        type="button"
                        className="rounded border border-border px-2 py-1 text-xs hover:bg-muted"
                        onClick={() => ackEvent.mutate(e.id)}
                      >
                        Ack
                      </button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
          {!events.isLoading && tableItems.length === 0 ? (
            <p className="py-4 text-sm text-muted-foreground">No active events.</p>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-6 space-y-3">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold">SMTP notifications (JSON) + test</h2>
            <div className="flex items-center gap-2">
              <button
                type="button"
                className="rounded border border-border px-2 py-1 text-xs hover:bg-muted"
                onClick={() => {
                  setSmtpDraft(smtpLoaded);
                  setSmtpTouched(false);
                }}
              >
                Reset
              </button>
              <button
                type="button"
                className="rounded bg-primary px-2 py-1 text-xs text-primary-foreground"
                onClick={() => {
                  const parsed = JSON.parse(smtpDraft) as NotificationsCfg;
                  saveNotifications.mutate(parsed);
                }}
              >
                Save SMTP
              </button>
              <button
                type="button"
                className="rounded border border-border px-2 py-1 text-xs hover:bg-muted"
                onClick={() => testEmail.mutate()}
              >
                Test email
              </button>
            </div>
          </div>
          <textarea
            className="min-h-[220px] w-full rounded-md border border-border bg-background p-3 font-mono text-xs"
            value={smtpDraft}
            onChange={(e) => {
              setSmtpDraft(e.target.value);
              setSmtpTouched(true);
            }}
          />
          {testEmail.data ? (
            <p className={`text-xs ${testEmail.data.ok ? "text-emerald-600" : "text-destructive"}`}>
              Test email: {testEmail.data.message}
            </p>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-6 space-y-3">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold">Full BAS backup / restore (JSON)</h2>
            <div className="flex items-center gap-2">
              <button
                type="button"
                className="rounded border border-border px-2 py-1 text-xs hover:bg-muted"
                onClick={() => exportBackup.mutate()}
              >
                Export backup
              </button>
              <button
                type="button"
                className="rounded bg-primary px-2 py-1 text-xs text-primary-foreground"
                onClick={() => importBackup.mutate(JSON.parse(restorePayload))}
              >
                Restore backup
              </button>
            </div>
          </div>
          <textarea
            className="min-h-[240px] w-full rounded-md border border-border bg-background p-3 font-mono text-xs"
            value={restorePayload}
            onChange={(e) => setRestorePayload(e.target.value)}
            placeholder="Click Export backup, then store this JSON in git/secure storage. Restore into a blank BAS Lite instance with Restore backup."
          />
          <p className="text-xs text-muted-foreground">
            Includes driver configs, schedule, alarm definitions/state, notification config, and discovery export artifacts.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-6 space-y-3">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold">Alarm definitions (JSON)</h2>
            <div className="flex items-center gap-2">
              <button
                type="button"
                className="rounded border border-border px-2 py-1 text-xs hover:bg-muted"
                onClick={() => {
                  setDraft(loadedDraft);
                  setDraftTouched(false);
                }}
              >
                Reset
              </button>
              <button
                type="button"
                className="rounded bg-primary px-2 py-1 text-xs text-primary-foreground"
                onClick={() => {
                  const parsed = JSON.parse(draft) as AlarmDefinition[];
                  saveDefinitions.mutate(parsed);
                }}
              >
                Save
              </button>
            </div>
          </div>
          <textarea
            className="min-h-[280px] w-full rounded-md border border-border bg-background p-3 font-mono text-xs"
            value={draft}
            onChange={(e) => {
              setDraft(e.target.value);
              setDraftTouched(true);
            }}
          />
          <p className="text-xs text-muted-foreground">
            Suggested pattern: one row per point with threshold/comparison/severity. This JSON can be exported to an LLM
            workflow, edited, then pasted back here.
          </p>
          {saveDefinitions.isError ? (
            <p className="text-xs text-destructive">{(saveDefinitions.error as Error).message}</p>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}

