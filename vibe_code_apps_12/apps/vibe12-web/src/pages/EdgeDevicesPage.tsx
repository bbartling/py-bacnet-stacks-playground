import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../lib/api-client";
import { logger } from "../lib/logger";
import { TopBar } from "../components/layout/TopBar";
import { StatusDot } from "../components/StatusDot";

type BuildingRow = {
  site_id: string;
  building_id: string;
  ingest_status: string;
  series_total: number;
  series_flowing: number;
  cloud_ingest_ok: boolean;
  last_activity_ms: number;
};

type SeriesRow = {
  series_id: string;
  point_id?: string;
  system_id?: string;
  source?: string;
  ingest_status?: string;
  freshness?: { status: string; label: string; age_minutes?: number | null };
  last_ts_ms?: number;
  last_value?: number | null;
  has_brick_timeseries_ref?: boolean;
  entity_id?: string;
};

function fmtTs(ms: number) {
  if (!ms) return "—";
  return new Date(ms).toISOString().replace("T", " ").slice(0, 19) + " UTC";
}

export function EdgeDevicesPage() {
  const [buildings, setBuildings] = useState<BuildingRow[]>([]);
  const [series, setSeries] = useState<SeriesRow[]>([]);
  const [thresholds, setThresholds] = useState<Record<string, number>>({});

  const load = useCallback(async () => {
    const data = await apiFetch<{
      buildings: BuildingRow[];
      series: SeriesRow[];
      freshness_thresholds_minutes: Record<string, number>;
    }>("/api/edge-devices");
    setBuildings(data.buildings || []);
    setSeries(data.series || []);
    setThresholds(data.freshness_thresholds_minutes || {});
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
        subtitle="BACnet / IoT ingest health · green &lt;20m · yellow 20–40 · orange 40–60 · red &gt;60m"
      />
      <div className="card toolbar-card">
        <button type="button" onClick={() => void load()}>
          Refresh
        </button>
        <span className="muted">
          Thresholds (min): green &lt;{thresholds.green ?? 20}, yellow &lt;{thresholds.yellow ?? 40},
          orange &lt;{thresholds.orange ?? 60}, red after
        </span>
      </div>
      <div className="card">
        <h3 className="title">Buildings</h3>
        <table className="registry-table">
          <thead>
            <tr>
              <th />
              <th>Site / building</th>
              <th>Flowing</th>
              <th>Last activity</th>
            </tr>
          </thead>
          <tbody>
            {buildings.map((b) => (
              <tr key={`${b.site_id}-${b.building_id}`}>
                <td>
                  <StatusDot status={b.ingest_status} />
                </td>
                <td>
                  {b.site_id} / {b.building_id}
                </td>
                <td>
                  {b.series_flowing}/{b.series_total}
                </td>
                <td className="mono small">{fmtTs(b.last_activity_ms)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="card">
        <h3 className="title">Series ({series.length})</h3>
        <div className="registry-wrap edge-scroll">
          <table className="registry-table">
            <thead>
              <tr>
                <th />
                <th>Point</th>
                <th>Source</th>
                <th>Last value</th>
                <th>Last ingest</th>
                <th>BRICK entity</th>
              </tr>
            </thead>
            <tbody>
              {series.map((s) => (
                <tr key={s.series_id}>
                  <td>
                    <StatusDot
                      status={s.ingest_status || s.freshness?.status || "offline"}
                      title={s.freshness?.label}
                    />
                  </td>
                  <td className="mono small">
                    {s.point_id || s.series_id}
                    <br />
                    <span className="muted">{s.system_id}</span>
                  </td>
                  <td>{s.source || "—"}</td>
                  <td>{s.last_value != null ? String(s.last_value) : "—"}</td>
                  <td className="mono small">{fmtTs(s.last_ts_ms || 0)}</td>
                  <td className="mono small">{s.entity_id ? "✓" : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
