import { JsonTreeView } from "./JsonTreeView";

type HealthData = Record<string, unknown>;

function HealthSummary({ data }: { data: HealthData }) {
  const status = String(data.status ?? "unknown");
  const ok = status === "ok";
  const features = Array.isArray(data.features) ? (data.features as string[]) : [];

  return (
    <div className="health-summary">
      <div className="health-summary-top">
        <span className={`health-status-pill ${ok ? "ok" : "warn"}`}>{status}</span>
        <span className="health-app">{String(data.app ?? "vibe12")}</span>
        {data.deploy_revision != null ? (
          <span className="health-revision muted">rev {String(data.deploy_revision)}</span>
        ) : null}
      </div>
      <dl className="health-kv-grid">
        {data.table != null ? (
          <>
            <dt>DynamoDB</dt>
            <dd className="mono small">{String(data.table)}</dd>
          </>
        ) : null}
        {data.mqtt_topic_pattern != null ? (
          <>
            <dt>MQTT topic</dt>
            <dd className="mono small">{String(data.mqtt_topic_pattern)}</dd>
          </>
        ) : null}
        {data.numpy_available != null ? (
          <>
            <dt>NumPy</dt>
            <dd>{data.numpy_available ? "available" : "unavailable"}</dd>
          </>
        ) : null}
      </dl>
      {features.length > 0 ? (
        <div className="health-features">
          <span className="muted health-features-label">Features</span>
          <div className="json-chip-list">
            {features.map((f) => (
              <span key={f} className="json-chip json-feature-chip">
                {f.replace(/_/g, " ")}
              </span>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function HealthPanel({ data }: { data: HealthData | null }) {
  if (!data) {
    return <p className="muted">Loading health…</p>;
  }

  return (
    <div className="health-panel">
      <HealthSummary data={data} />
      <details className="health-tree-section" open>
        <summary className="health-tree-toggle">Full configuration tree</summary>
        <JsonTreeView data={data} openDepth={1} />
      </details>
    </div>
  );
}
