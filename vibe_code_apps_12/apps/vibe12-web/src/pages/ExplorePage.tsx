import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Plotly from "plotly.js-dist-min";
import { apiFetch } from "../lib/api-client";
import { logger } from "../lib/logger";
import { plotlyBaseLayout, plotlyThemeColors } from "../lib/plotly-theme";
import { TopBar } from "../components/layout/TopBar";
import { StatusDot } from "../components/StatusDot";
import { useTheme } from "../contexts/theme-context";

type CatalogSeries = {
  series_id: string;
  site_id: string;
  building_id: string;
  point_id?: string;
  system_id?: string;
  source?: string;
  brick_class?: string;
  brick_tag?: string;
  object_name?: string;
  unit?: string;
  last_value?: number | null;
  freshness?: { status: string; label: string; age_minutes?: number | null };
  has_brick_timeseries_ref?: boolean;
};

type SeriesPoint = { ts_ms: number; value: number; unit?: string };

function formatBrickClass(brickClass?: string): string {
  if (!brickClass) return "—";
  return brickClass.replace(/_/g, " ");
}

function seriesLabel(s: CatalogSeries): string {
  return s.object_name || s.brick_tag || s.point_id || s.series_id.split("#").slice(-1)[0] || "—";
}

export function ExplorePage() {
  const { theme } = useTheme();
  const chartRef = useRef<HTMLDivElement>(null);
  const [catalog, setCatalog] = useState<CatalogSeries[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [hours, setHours] = useState(24);
  const [status, setStatus] = useState("—");

  const labelBySeries = useMemo(() => {
    const m = new Map<string, string>();
    for (const s of catalog) {
      m.set(s.series_id, seriesLabel(s));
    }
    return m;
  }, [catalog]);

  const loadCatalog = useCallback(async () => {
    const data = await apiFetch<{ series: CatalogSeries[] }>("/api/telemetry/catalog");
    const list = data.series || [];
    setCatalog(list);
    if (!selected.length && list.length) {
      setSelected([list[0].series_id]);
    }
  }, [selected.length]);

  const plotSelected = useCallback(async () => {
    if (!selected.length || !chartRef.current) {
      setStatus("Select at least one series.");
      return;
    }
    const url = `/api/series?series_ids=${encodeURIComponent(selected.join(","))}&hours=${hours}`;
    const data = await apiFetch<{ series: Record<string, SeriesPoint[]> }>(url);
    const colors = plotlyThemeColors(theme).traceColors;
    const traces = Object.entries(data.series || {}).map(([sid, pts], i) => ({
      x: pts.map((p) => new Date(p.ts_ms)),
      y: pts.map((p) => p.value),
      type: "scatter" as const,
      mode: "lines" as const,
      name: labelBySeries.get(sid) || sid.split("#").slice(-2).join("/") || sid,
      line: { color: colors[i % colors.length], width: 2 },
    }));
    if (!traces.length) {
      setStatus("No samples in window.");
      return;
    }
    await Plotly.react(
      chartRef.current,
      traces,
      plotlyBaseLayout(theme, { yaxis: { title: "Value" } }),
      { responsive: true, displayModeBar: true },
    );
    setStatus(`${selected.length} series · ${hours}h · raw samples (no FDD required)`);
  }, [selected, hours, theme, labelBySeries]);

  useEffect(() => {
    void loadCatalog().catch((e) => logger.error("explore", "catalog", e));
  }, [loadCatalog]);

  useEffect(() => {
    void plotSelected().catch((e) => logger.error("explore", "plot", e));
    return () => {
      if (chartRef.current) Plotly.purge(chartRef.current);
    };
  }, [plotSelected]);

  function toggle(id: string) {
    setSelected((cur) =>
      cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id].slice(0, 8),
    );
  }

  return (
    <div className="stack-page explore-page">
      <TopBar
        title="Explore raw data"
        subtitle="Plot any ingested series — no BRICK model or FDD rules required"
      />
      <div className="card toolbar-card">
        <label>
          History
          <select value={hours} onChange={(e) => setHours(Number(e.target.value))}>
            {[6, 24, 48, 168].map((h) => (
              <option key={h} value={h}>
                {h} h
              </option>
            ))}
          </select>
        </label>
        <button type="button" onClick={() => void plotSelected()}>
          Refresh chart
        </button>
        <button type="button" className="secondary-btn" onClick={() => void loadCatalog()}>
          Reload catalog
        </button>
        <span className="muted">{status}</span>
      </div>
      <div className="explore-stack">
        <div className="card explore-list">
          <h3 className="title">Telemetry catalog ({catalog.length})</h3>
          <div className="registry-wrap explore-scroll">
            <table className="registry-table">
              <thead>
                <tr>
                  <th />
                  <th>Series</th>
                  <th>Point name</th>
                  <th>BRICK class</th>
                  <th>Last</th>
                  <th>BRICK ref</th>
                </tr>
              </thead>
              <tbody>
                {catalog.map((s) => (
                  <tr
                    key={s.series_id}
                    className={selected.includes(s.series_id) ? "row-selected" : ""}
                    onClick={() => toggle(s.series_id)}
                  >
                    <td>
                      <StatusDot
                        status={s.freshness?.status || "offline"}
                        title={s.freshness?.label}
                      />
                    </td>
                    <td className="mono small">
                      {s.site_id}/{s.building_id}
                      <br />
                      <span className="muted">{s.system_id}/</span>
                      {s.point_id || s.series_id.split("#").slice(-1)[0]}
                    </td>
                    <td className="point-name-cell">{s.object_name || s.brick_tag || "—"}</td>
                    <td className="brick-class-cell" title={s.brick_class}>
                      {formatBrickClass(s.brick_class)}
                    </td>
                    <td>
                      {s.last_value != null ? `${s.last_value}${s.unit ? ` ${s.unit}` : ""}` : "—"}
                    </td>
                    <td>{s.has_brick_timeseries_ref ? "yes" : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <div className="card chart-card explore-chart">
          <div ref={chartRef} className="plot-host explore-plot-host" />
        </div>
      </div>
    </div>
  );
}
