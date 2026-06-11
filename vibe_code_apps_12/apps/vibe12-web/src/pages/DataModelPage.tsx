import { useCallback, useEffect, useState } from "react";
import { apiFetch, apiFetchText } from "../lib/api-client";
import { downloadJson } from "../lib/rule-lab-console";
import { logger } from "../lib/logger";
import { useSite } from "../contexts/site-context";
import { TopBar } from "../components/layout/TopBar";

type PointRow = {
  series_id?: string;
  system_id?: string;
  point_id?: string;
  brick_class?: string;
  unit?: string;
  entity_id?: string;
  external_ref?: string;
};

export function DataModelPage() {
  const { siteId, buildingId } = useSite();
  const base = `/api/data-model/${encodeURIComponent(siteId)}/${encodeURIComponent(buildingId)}`;
  const [exportJson, setExportJson] = useState("");
  const [importJson, setImportJson] = useState("");
  const [status, setStatus] = useState("");
  const [ttl, setTtl] = useState("");
  const [points, setPoints] = useState<PointRow[]>([]);

  const loadRegistry = useCallback(async () => {
    const data = await apiFetch<{ points: PointRow[] }>(
      `/api/points/${encodeURIComponent(siteId)}/${encodeURIComponent(buildingId)}`,
    );
    setPoints(data.points || []);
    logger.info("datamodel", `registry ${(data.points || []).length} points`);
  }, [siteId, buildingId]);

  useEffect(() => {
    void loadRegistry().catch((e) => logger.error("datamodel", "registry failed", e));
  }, [loadRegistry]);

  async function doExport() {
    const model = await apiFetch<Record<string, unknown>>(`${base}/export`);
    setExportJson(JSON.stringify(model, null, 2));
    setStatus(`Exported ${(model.points as unknown[])?.length ?? 0} points.`);
  }

  async function doImport() {
    const payload = JSON.parse(importJson);
    await apiFetch(`${base}/import`, {
      method: "POST",
      body: JSON.stringify({ payload, replace: true }),
    });
    setStatus("Import OK.");
    await doExport();
    await loadRegistry();
  }

  async function syncTtl() {
    const text = await apiFetchText(`${base}/ttl?sync=true`);
    setTtl(text);
    setStatus(`TTL synced (${text.length} bytes).`);
  }

  return (
    <div className="stack-page">
      <TopBar
        title="Data Model"
        subtitle="BRICK canonical model · demo bench BACnet device 5007 · OA-H, OA-T, DUCT-T, STAT-ZN-T"
      />
      <div className="card toolbar-card">
        <button type="button" onClick={() => void doExport()}>Load export</button>
        <button
          type="button"
          className="secondary-btn"
          disabled={!exportJson}
          onClick={() => {
            try {
              const data = JSON.parse(exportJson);
              downloadJson(`canonical-model-${siteId}-${buildingId}.json`, data);
              setStatus("Downloaded JSON file.");
            } catch {
              setStatus("Export JSON invalid — click Load export first.");
            }
          }}
        >
          Download JSON
        </button>
        <button type="button" className="secondary-btn" onClick={() => void loadRegistry()}>Refresh registry</button>
        <button type="button" className="secondary-btn" onClick={() => void syncTtl()}>Sync TTL</button>
        <span className="muted">{status}</span>
      </div>
      <div className="card">
        <h3 className="title">Time-series registry</h3>
        <div className="registry-wrap">
          <table className="registry-table">
            <thead>
              <tr>
                <th>series_id</th>
                <th>system</th>
                <th>point</th>
                <th>BRICK</th>
                <th>entity_id</th>
                <th>unit</th>
              </tr>
            </thead>
            <tbody>
              {points.length === 0 ? (
                <tr>
                  <td colSpan={6} className="muted">No points — ingest MQTT first.</td>
                </tr>
              ) : (
                points.map((p) => (
                  <tr key={p.series_id}>
                    <td>{p.series_id}</td>
                    <td>{p.system_id}</td>
                    <td>{p.point_id}</td>
                    <td>{p.brick_class || "—"}</td>
                    <td className="mono small">{p.entity_id || p.external_ref || "—"}</td>
                    <td>{p.unit}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
      <div className="grid-two">
        <div className="card">
          <h3 className="title">Export</h3>
          <textarea className="json-area" readOnly value={exportJson} placeholder="Export JSON…" />
        </div>
        <div className="card">
          <h3 className="title">Import</h3>
          <textarea
            className="json-area"
            value={importJson}
            onChange={(e) => setImportJson(e.target.value)}
            placeholder='{"sites":[],"equipment":[],"points":[]}'
          />
          <button type="button" style={{ marginTop: 8 }} onClick={() => void doImport()}>
            Import JSON
          </button>
        </div>
      </div>
      <details className="card ttl-details">
        <summary>BRICK TTL (read-only)</summary>
        <pre className="ttl-pre">{ttl || "Click Sync TTL."}</pre>
      </details>
    </div>
  );
}
