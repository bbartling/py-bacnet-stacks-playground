import { useCallback, useEffect, useRef, useState } from "react";
import Plotly from "plotly.js-dist-min";
import { apiFetch } from "../lib/api-client";
import { logger } from "../lib/logger";
import { TopBar } from "../components/layout/TopBar";
import { EdgeStatusPanel, type EdgeStatusPayload } from "../components/EdgeStatusPanel";
import { useSite } from "../contexts/site-context";
import { useTheme } from "../contexts/theme-context";
import { plotlyBaseLayout, plotlyThemeColors } from "../lib/plotly-theme";

type Reading = {
  ts_ms: number;
  ts?: string;
  degF: number;
  degC: number;
};

type ReadingsResponse = {
  readings: Reading[];
  fdd_open?: { fdd_status?: string };
  chart_truncated?: boolean;
};

const HOURS_OPTS = [6, 24, 48, 168];

export function DashboardPage() {
  const { theme } = useTheme();
  const { siteId, buildingId } = useSite();
  const chartRef = useRef<HTMLDivElement>(null);
  const [edgeStatus, setEdgeStatus] = useState<EdgeStatusPayload | null>(null);
  const [showChart, setShowChart] = useState(false);
  const [hours, setHours] = useState(24);
  const [unit, setUnit] = useState<"imperial" | "metric">("imperial");
  const [rolling, setRolling] = useState(1);
  const [chartStatus, setChartStatus] = useState("");
  const [latest, setLatest] = useState<{ c: string; f: string }>({ c: "—", f: "—" });
  const [fddStatus, setFddStatus] = useState("PENDING");
  const [loadingChart, setLoadingChart] = useState(false);

  const loadEdge = useCallback(async () => {
    const data = await apiFetch<EdgeStatusPayload>("/api/edge-devices");
    setEdgeStatus(data);
  }, []);

  const loadChart = useCallback(async () => {
    if (!showChart) return;
    setLoadingChart(true);
    const url =
      `/api/readings?site_id=${encodeURIComponent(siteId)}&building_id=${encodeURIComponent(buildingId)}` +
      `&hours=${hours}&rolling_avg_minutes=${rolling}&temp_unit=${unit}`;
    try {
      const data = await apiFetch<ReadingsResponse>(url);
      const pts = data.readings || [];
      setFddStatus(data.fdd_open?.fdd_status || "PENDING");
      setChartStatus(
        `${pts.length} pts · ${hours}h` + (data.chart_truncated ? " (downsampled)" : ""),
      );
      if (pts.length) {
        const last = pts[pts.length - 1];
        setLatest({ c: last.degC.toFixed(2), f: last.degF.toFixed(2) });
      }
      if (chartRef.current && pts.length) {
        const y = pts.map((p) => (unit === "metric" ? p.degC : p.degF));
        const x = pts.map((p) => new Date(p.ts_ms));
        const sym = unit === "metric" ? "°C" : "°F";
        const primary = plotlyThemeColors(theme).primary;
        await Plotly.react(
          chartRef.current,
          [
            {
              x,
              y,
              type: "scatter",
              mode: "lines",
              name: `Temperature (${sym})`,
              line: { color: primary, width: 2 },
            },
          ],
          plotlyBaseLayout(theme, { yaxis: { title: sym } }),
          { responsive: true, displayModeBar: true },
        );
      }
    } catch (e) {
      setChartStatus("Chart load failed");
      logger.error("dashboard", "readings failed", e);
    } finally {
      setLoadingChart(false);
    }
  }, [showChart, hours, unit, rolling, siteId, buildingId, theme]);

  useEffect(() => {
    void loadEdge().catch((e) => logger.error("dashboard", "edge", e));
    const id = window.setInterval(() => void loadEdge(), 60000);
    return () => window.clearInterval(id);
  }, [loadEdge]);

  useEffect(() => {
    void loadChart();
    if (!showChart) return;
    const id = window.setInterval(() => void loadChart(), 30000);
    return () => {
      window.clearInterval(id);
      if (chartRef.current) Plotly.purge(chartRef.current);
    };
  }, [loadChart, showChart]);

  return (
    <div className="stack-page">
      <TopBar
        title="Dashboard"
        subtitle="Edge ingest + optional IoT thing status · temperature chart optional"
      />
      <div className="card">
        <div className="dashboard-card-header">
          <h3 className="title">Edge &amp; cloud ingest</h3>
          <button type="button" className="secondary-btn" onClick={() => void loadEdge()}>
            Refresh status
          </button>
        </div>
        <EdgeStatusPanel data={edgeStatus} compact showSeriesLink />
      </div>

      <div className="card toolbar-card">
        <button
          type="button"
          className={showChart ? "secondary-btn" : ""}
          onClick={() => setShowChart((v) => !v)}
        >
          {showChart ? "Hide temperature chart" : "Show temperature chart"}
        </button>
        {showChart ? (
          <>
            <label>
              History
              <select value={hours} onChange={(e) => setHours(Number(e.target.value))}>
                {HOURS_OPTS.map((h) => (
                  <option key={h} value={h}>
                    {h} h
                  </option>
                ))}
              </select>
            </label>
            <label>
              Display
              <select value={unit} onChange={(e) => setUnit(e.target.value as "imperial" | "metric")}>
                <option value="imperial">°F</option>
                <option value="metric">°C</option>
              </select>
            </label>
            <button type="button" onClick={() => void loadChart()} disabled={loadingChart}>
              {loadingChart ? "Loading…" : "Refresh chart"}
            </button>
            <span className="muted">{chartStatus}</span>
          </>
        ) : null}
      </div>

      {showChart ? (
        <>
          <div className="metric-row">
            <div className="card metric-card">
              <div className="muted">°C</div>
              <div className="metric-val">{latest.c}</div>
            </div>
            <div className="card metric-card">
              <div className="muted">°F</div>
              <div className="metric-val">{latest.f}</div>
            </div>
            <div className="card metric-card">
              <div className="muted">FDD status</div>
              <div className={`metric-val fdd-chip fdd-${fddStatus}`}>{fddStatus}</div>
            </div>
          </div>
          <div className="card chart-card">
            <div ref={chartRef} className="plot-host" />
          </div>
        </>
      ) : null}
    </div>
  );
}
