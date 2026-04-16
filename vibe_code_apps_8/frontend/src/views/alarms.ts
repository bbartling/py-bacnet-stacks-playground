import { html, render } from "lit-html";
import { apiFetch } from "../api";
import { subscribeTopics } from "../topics";
import { prettyJson } from "../util";
import type { MountFn } from "./types";

type AlarmEvent = {
  id: string;
  severity: string;
  state: string;
  message: string;
  triggeredAt: string;
  deviceId: string;
  pointId: string;
};

type AlarmDefinition = Record<string, unknown>;

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
  emailNotificationSupported?: boolean;
  passwordStored?: boolean;
  passwordFromEnv?: boolean;
};

export const mountAlarms: MountFn = (outlet) => {
  let events: AlarmEvent[] = [];
  let eventsLoading = true;
  let definitionsDraft = "";
  let definitionsTouched = false;
  let smtpDraft = "";
  let smtpTouched = false;
  let restorePayload = "";
  let notificationsMeta: NotificationsCfg | null = null;
  let testEmailMsg: string | null = null;
  let saveDefErr: string | null = null;
  let cancelled = false;

  const paint = () => {
    render(
      html`
        <div class="space-y-6">
          <div>
            <h1 class="text-2xl font-semibold tracking-tight">Alarms</h1>
            <p class="mt-1 text-sm text-muted-foreground">
              Supervisory alarm definitions and runtime events. Keep faults analytics separate on the Faults tab.
            </p>
          </div>
          <div class="rounded-xl border border-border/60 bg-card/50 shadow-sm">
            <div class="p-6 pt-6">
              <div class="mb-3 flex items-center justify-between gap-2">
                <h2 class="text-sm font-semibold">Active alarm events</h2>
              </div>
              ${eventsLoading
                ? html`<div class="h-40 w-full animate-pulse rounded-md bg-muted"></div>`
                : html`
                    <div class="overflow-x-auto rounded-md border border-border/50">
                      <table class="w-full border-collapse text-sm">
                        <thead>
                          <tr class="border-b border-border/60 bg-muted/40 text-left text-xs text-muted-foreground">
                            <th class="px-3 py-2 font-medium">Severity</th>
                            <th class="px-3 py-2 font-medium">State</th>
                            <th class="px-3 py-2 font-medium">Message</th>
                            <th class="px-3 py-2 font-medium">Point</th>
                            <th class="px-3 py-2 font-medium">When</th>
                            <th class="px-3 py-2 text-right font-medium">Action</th>
                          </tr>
                        </thead>
                        <tbody>
                          ${events.map(
                            (e) => html`
                              <tr class="border-b border-border/40 last:border-0">
                                <td class="px-3 py-2 text-xs font-medium uppercase">${e.severity}</td>
                                <td class="px-3 py-2 text-xs">${e.state}</td>
                                <td class="px-3 py-2 text-sm">${e.message}</td>
                                <td class="px-3 py-2 font-mono text-xs">${e.pointId}</td>
                                <td class="px-3 py-2 text-xs text-muted-foreground">${e.triggeredAt}</td>
                                <td class="px-3 py-2 text-right">
                                  <button
                                    type="button"
                                    class="rounded border border-border px-2 py-1 text-xs hover:bg-muted"
                                    @click=${() => void ack(e.id)}
                                  >
                                    Ack
                                  </button>
                                </td>
                              </tr>
                            `,
                          )}
                        </tbody>
                      </table>
                    </div>
                  `}
              ${!eventsLoading && events.length === 0
                ? html`<p class="py-4 text-sm text-muted-foreground">No active events.</p>`
                : null}
            </div>
          </div>
          <div class="rounded-xl border border-border/60 bg-card/50 shadow-sm">
            <div class="space-y-3 p-6 pt-6">
              <div class="flex flex-wrap items-center justify-between gap-2">
                <h2 class="text-sm font-semibold">SMTP notifications (JSON) + test</h2>
                <div class="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    class="rounded border border-border px-2 py-1 text-xs hover:bg-muted"
                    @click=${() => {
                      const base = (notificationsMeta?.smtp ?? {}) as NotificationsCfg["smtp"];
                      const merged: NotificationsCfg = {
                        smtp: {
                          ...base,
                          enabled: true,
                          host: "smtp.gmail.com",
                          port: 587,
                          starttls: true,
                          ssl: false,
                          timeoutSec: 8,
                        },
                      };
                      smtpDraft = prettyJson(merged);
                      smtpTouched = true;
                      paint();
                    }}
                  >
                    Use Gmail preset
                  </button>
                  <button
                    type="button"
                    class="rounded border border-border px-2 py-1 text-xs hover:bg-muted"
                    @click=${() => void resetSmtp()}
                  >
                    Reset
                  </button>
                  <button
                    type="button"
                    class="rounded bg-primary px-2 py-1 text-xs text-primary-foreground"
                    @click=${() => void saveSmtp()}
                  >
                    Save SMTP
                  </button>
                  <button
                    type="button"
                    class="rounded border border-border px-2 py-1 text-xs hover:bg-muted"
                    @click=${() => void testEmail()}
                  >
                    Test email
                  </button>
                </div>
              </div>
              <textarea
                class="min-h-[220px] w-full rounded-md border border-border bg-background p-3 font-mono text-xs"
                .value=${smtpDraft}
                @input=${(e: Event) => {
                  smtpDraft = (e.target as HTMLTextAreaElement).value;
                  smtpTouched = true;
                }}
                spellcheck=${false}
              ></textarea>
              <p class="text-xs text-muted-foreground">
                Password is masked on read and not returned by the API. To rotate, replace
                <code class="rounded bg-muted px-1">"password": "********"</code> with a new secret.
              </p>
              <p class="text-xs text-muted-foreground">
                Stored password: ${notificationsMeta?.passwordStored ? "yes" : "no"} · source:
                ${notificationsMeta?.passwordFromEnv ? "env (BAS_LITE_SMTP_PASSWORD)" : "notifications config"}
              </p>
              ${testEmailMsg
                ? html`<p class="text-xs text-emerald-600">${testEmailMsg}</p>`
                : null}
            </div>
          </div>
          <div class="rounded-xl border border-border/60 bg-card/50 shadow-sm">
            <div class="space-y-3 p-6 pt-6">
              <div class="flex flex-wrap items-center justify-between gap-2">
                <h2 class="text-sm font-semibold">Full BAS backup / restore (JSON)</h2>
                <div class="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    class="rounded border border-border px-2 py-1 text-xs hover:bg-muted"
                    @click=${() => void exportBackup()}
                  >
                    Export backup
                  </button>
                  <button
                    type="button"
                    class="rounded bg-primary px-2 py-1 text-xs text-primary-foreground"
                    @click=${() => void importBackup()}
                  >
                    Restore backup
                  </button>
                </div>
              </div>
              <textarea
                class="min-h-[240px] w-full rounded-md border border-border bg-background p-3 font-mono text-xs"
                .value=${restorePayload}
                @input=${(e: Event) => {
                  restorePayload = (e.target as HTMLTextAreaElement).value;
                }}
                placeholder="Click Export backup, then store this JSON in git/secure storage."
                spellcheck=${false}
              ></textarea>
            </div>
          </div>
          <div class="rounded-xl border border-border/60 bg-card/50 shadow-sm">
            <div class="space-y-3 p-6 pt-6">
              <div class="flex flex-wrap items-center justify-between gap-2">
                <h2 class="text-sm font-semibold">Alarm definitions (JSON)</h2>
                <div class="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    class="rounded border border-border px-2 py-1 text-xs hover:bg-muted"
                    @click=${() => {
                      definitionsDraft = loadedDefinitionsFromServer();
                      definitionsTouched = false;
                      saveDefErr = null;
                      paint();
                    }}
                  >
                    Reset
                  </button>
                  <button
                    type="button"
                    class="rounded bg-primary px-2 py-1 text-xs text-primary-foreground"
                    @click=${() => void saveDefinitions()}
                  >
                    Save
                  </button>
                </div>
              </div>
              <textarea
                class="min-h-[280px] w-full rounded-md border border-border bg-background p-3 font-mono text-xs"
                .value=${definitionsDraft}
                @input=${(e: Event) => {
                  definitionsDraft = (e.target as HTMLTextAreaElement).value;
                  definitionsTouched = true;
                }}
                spellcheck=${false}
              ></textarea>
              ${saveDefErr ? html`<p class="text-xs text-destructive">${saveDefErr}</p>` : null}
            </div>
          </div>
        </div>
      `,
      outlet,
    );
  };

  let defItems: AlarmDefinition[] = [];

  const loadedDefinitionsFromServer = () => prettyJson(defItems);

  const loadEvents = async () => {
    eventsLoading = true;
    paint();
    try {
      const res = await apiFetch<{ items: AlarmEvent[] }>("api/alarms/events");
      if (cancelled) return;
      events = res.items ?? [];
    } catch {
      if (!cancelled) events = [];
    } finally {
      if (!cancelled) eventsLoading = false;
      paint();
    }
  };

  const loadDefinitions = async () => {
    try {
      const res = await apiFetch<{ items: AlarmDefinition[] }>("api/alarms/definitions");
      if (cancelled) return;
      defItems = res.items ?? [];
      if (!definitionsTouched) definitionsDraft = prettyJson(defItems);
    } catch {
      /* ignore */
    }
    paint();
  };

  const loadNotifications = async () => {
    try {
      notificationsMeta = await apiFetch<NotificationsCfg>("api/notifications/config");
      if (cancelled) return;
      if (!smtpTouched) smtpDraft = prettyJson(notificationsMeta ?? { smtp: {} });
    } catch {
      /* ignore */
    }
    paint();
  };

  const resetSmtp = async () => {
    await loadNotifications();
    smtpTouched = false;
  };

  const saveSmtp = async () => {
    try {
      const parsed = JSON.parse(smtpDraft) as NotificationsCfg;
      await apiFetch("api/notifications/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(parsed),
      });
      smtpTouched = false;
      await loadNotifications();
    } catch (e) {
      testEmailMsg = e instanceof Error ? e.message : "Invalid JSON";
      paint();
    }
  };

  const testEmail = async () => {
    testEmailMsg = null;
    try {
      const res = await apiFetch<{ ok: boolean; message: string }>("api/notifications/test-email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      testEmailMsg = `Test email: ${res.message}`;
    } catch (e) {
      testEmailMsg = e instanceof Error ? e.message : "Test failed";
    }
    paint();
  };

  const exportBackup = async () => {
    try {
      const d = await apiFetch<{ status: string; payload: unknown }>("api/backup/export");
      restorePayload = prettyJson(d.payload);
    } catch (e) {
      restorePayload = e instanceof Error ? e.message : "export failed";
    }
    paint();
  };

  const importBackup = async () => {
    try {
      const payload = JSON.parse(restorePayload) as unknown;
      await apiFetch("api/backup/restore", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ payload }),
      });
      await Promise.all([loadEvents(), loadDefinitions(), loadNotifications()]);
    } catch (e) {
      restorePayload = e instanceof Error ? e.message : "restore failed";
      paint();
    }
  };

  const saveDefinitions = async () => {
    saveDefErr = null;
    try {
      const parsed = JSON.parse(definitionsDraft) as AlarmDefinition[];
      await apiFetch("api/alarms/definitions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ items: parsed }),
      });
      definitionsTouched = false;
      await loadDefinitions();
    } catch (e) {
      saveDefErr = e instanceof Error ? e.message : "Save failed";
      paint();
    }
  };

  const ack = async (eventId: string) => {
    await apiFetch("api/alarms/ack", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ eventId }),
    });
    await loadEvents();
  };

  void loadEvents();
  void loadDefinitions();
  void loadNotifications();

  const unsub = subscribeTopics((topic) => {
    if (topic === "alarms.updated") void loadEvents();
  });
  const iv = window.setInterval(() => void loadEvents(), 15_000);
  paint();

  return () => {
    cancelled = true;
    window.clearInterval(iv);
    unsub();
    render(html``, outlet);
  };
};
