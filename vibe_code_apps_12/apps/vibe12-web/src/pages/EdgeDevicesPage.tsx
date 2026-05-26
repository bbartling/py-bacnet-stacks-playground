import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../lib/api-client";
import { logger } from "../lib/logger";
import { TopBar } from "../components/layout/TopBar";
import { StatusDot } from "../components/StatusDot";
import { EdgeStatusPanel, type EdgeStatusPayload } from "../components/EdgeStatusPanel";

type SeriesRow = {
  series_id: string;
  point_id?: string;
  system_id?: string;
  source?: string;
  object_name?: string;
  brick_class?: string;
  ingest_status?: string;
  freshness?: { status: string; label: string };
  last_ts_ms?: number;
  last_value?: number | null;
};

function fmtTs(ms: number) {
  if (!ms) return "—";
  return new Date(ms).toISOString().replace("T", " ").slice(0, 19) + " UTC";
}

export function EdgeDevicesPage() {
  const [payload, setPayload] = useState<EdgeStatusPayload | null>(null);
  const [series, setSeries] = useState<SeriesRow[]>([]);

  const load = useCallback(async () => {
    const data = await apiFetch<EdgeStatusPayload & { series: SeriesRow[] }>("/api/edge-devices");
    setPayload(data);
    setSeries(data.series || []);
    logger.info("edge", `${(data.series || []).length} series`);
  }, []);

  useEffect(() => {
    void load().catch((e) => logger.error("edge", "load", e));
    const id = window.setInterval(() => void load(), 60000);
    return () => window.clearInterval(id);
  }, [load]);

  return (
    <div className="stack-page">
      <TopBar
        title="Edge devices"
        subtitle="Telemetry freshness + optional AWS IoT Core thing connectivity"
      />
      <div className="card toolbar-card">
        <button type="button" onClick={() => void load()}>
          Refresh
        </button>
      </div>
      <div className="card">
        <EdgeStatusPanel data={payload} />
      </div>
      <div className="card">
        <h3 className="title">All series ({series.length})</h3>
        <div className="registry-wrap edge-scroll">
          <table className="registry-table">
            <thead>
              <tr>
                <th />
                <th>Point</th>
                <th>Source</th>
                <th>Last</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              {series.map((s) => (
                <tr key={s.series_id}>
                  <td>
                    <StatusDot status={s.ingest_status || s.freshness?.status || "offline"} />
                  </td>
                  <td className="mono small">
                    {s.object_name || s.point_id}
                    <br />
                    <span className="muted">{s.series_id}</span>
                  </td>
                  <td>{s.source || "—"}</td>
                  <td>
                    {s.last_value != null ? String(s.last_value) : "—"}
                  </td>
                  <td className="mono small">{fmtTs(s.last_ts_ms || 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
