import { useEffect, useState } from "react";
import { apiFetch } from "../lib/api-client";
import { TopBar } from "../components/layout/TopBar";

export function SystemPage() {
  const [health, setHealth] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    void apiFetch<Record<string, unknown>>("/api/health").then(setHealth);
  }, []);

  return (
    <div className="stack-page">
      <TopBar title="System" subtitle="Lambda health · deploy revision · troubleshooting" />
      <div className="card">
        <h3 className="title">Health</h3>
        <pre className="console-pre">{health ? JSON.stringify(health, null, 2) : "Loading…"}</pre>
      </div>
      <div className="card muted">
        <p>
          Browser logs: prefix <code>[vibe12]</code>. Use <code>?log=debug</code> or{" "}
          <code>localStorage.vibe12_log=debug</code> for API timing details.
        </p>
        <p>Auth: single engineer account via Lambda env — no Cognito cost.</p>
      </div>
    </div>
  );
}
