import { useEffect, useState } from "react";
import { apiFetch } from "../lib/api-client";
import { TopBar } from "../components/layout/TopBar";
import { StatusDot } from "../components/StatusDot";

type Check = {
  id: string;
  label: string;
  ok: boolean;
  detail?: string;
  hint?: string;
};

export function SystemPage() {
  const [health, setHealth] = useState<Record<string, unknown> | null>(null);
  const [deployment, setDeployment] = useState<{
    ready?: boolean;
    checks?: Check[];
    checks_ok?: number;
    checks_total?: number;
    series_with_brick_ref?: number;
    series_total?: number;
  } | null>(null);

  useEffect(() => {
    void apiFetch<Record<string, unknown>>("/api/health").then(setHealth);
    void apiFetch<typeof deployment>("/api/deployment/status").then(setDeployment);
  }, []);

  return (
    <div className="stack-page">
      <TopBar title="System" subtitle="Deploy readiness · Lambda health · troubleshooting" />
      <div className="card">
        <h3 className="title">Deployment readiness</h3>
        {deployment ? (
          <>
            <p className={deployment.ready ? "ok-text" : "warn-text"}>
              {deployment.ready ? "All checks passing" : "Incomplete — see items below"}
              {" · "}
              {deployment.checks_ok}/{deployment.checks_total} OK
              {deployment.series_total != null
                ? ` · BRICK refs ${deployment.series_with_brick_ref}/${deployment.series_total}`
                : ""}
            </p>
            <ul className="deploy-checklist">
              {(deployment.checks || []).map((c) => (
                <li key={c.id} className={c.ok ? "check-ok" : "check-fail"}>
                  <StatusDot status={c.ok ? "green" : "red"} title={c.label} />
                  <span>{c.label}</span>
                  {c.detail ? <span className="muted"> — {c.detail}</span> : null}
                  {!c.ok && c.hint ? <div className="hint muted">{c.hint}</div> : null}
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p className="muted">Loading…</p>
        )}
      </div>
      <div className="card">
        <h3 className="title">Health</h3>
        <pre className="console-pre">{health ? JSON.stringify(health, null, 2) : "Loading…"}</pre>
      </div>
    </div>
  );
}
