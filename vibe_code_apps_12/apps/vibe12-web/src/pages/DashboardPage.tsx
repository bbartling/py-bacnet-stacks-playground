import { useCallback, useEffect, useRef, useState } from "react";
import Plotly from "plotly.js-dist-min";
import { apiFetch } from "../lib/api-client";
import { logger } from "../lib/logger";
import { TopBar } from "../components/layout/TopBar";
import { useSite } from "../contexts/site-context";

type Reading = {
  ts_ms: number;
  ts?: string;
  degF: number;
  degC: number;
  temp?: number;
};

type ReadingsResponse = {
  readings: Reading[];
  count?: number;
  fdd_open?: { fdd_status?: string };
  display_temp_unit?: string;
  chart_truncated?: boolean;
  rules_meta?: Array<{ id: string; title: string; color: string; enabled?: boolean }>;
};

const HOURS_OPTS = [6, 24, 48, 168];

export function DashboardPage() {
  const { siteId, buildingId } = useSite();
  const chartRef = useRef<HTMLDivElement>(null);
  const [hours, setHours] = useState(24);
  const [unit, setUnit] = useState<"imperial" | "metric">("imperial");
  const [rolling, setRolling] = useState(1);
  const [status, setStatus] = useState("—");
  const [latest, setLatest] = useState<{ c: string; f: string }>({ c: "—", f: "—" });
  const [fddStatus, setFddStatus] = useState("PENDING");
  const [loading, setLoading] = useState(false);
  const lastFetch = useRef(0);

  const load = useCallback(async (silent = false) => {
    const now = Date.now();
    if (silent && now - lastFetch.current < 8000) return;
    lastFetch.current = now;
    if (!silent) setLoading(true);
    const url =
      `/api/readings?site_id=${encodeURIComponent(siteId)}&building_id=${encodeURIComponent(buildingId)}` +
      `&hours=${hours}&rolling_avg_minutes=${rolling}&temp_unit=${unit}`;
    try {
      const data = await apiFetch<ReadingsResponse>(url);
      const pts = data.readings || [];
      setFddStatus(data.fdd_open?.fdd_status || "PENDING");
      setStatus(
        `${pts.length} pts · ${hours}h lookback` +
          (data.chart_truncated ? " (chart downsampled)" : ""),
      );
      if (pts.length) {
        const last = pts[pts.length - 1];
        setLatest({ c: last.degC.toFixed(2), f: last.degF.toFixed(2) });
      }
      if (chartRef.current && pts.length) {
        const y = pts.map((p) => (unit === "metric" ? p.degC : p.degF));
        const x = pts.map((p) => new Date(p.ts_ms));
        const sym = unit === "metric" ? "°C" : "°F";
        await Plotly.react(
          chartRef.current,
          [
            {
              x,
              y,
              type: "scatter",
              mode: "lines",
              name: `Temperature (${sym})`,
              line: { color: "#4f78e8", width: 2 },
            },
          ],
          {
            paper_bgcolor: "#161b24",
            plot_bgcolor: "#161b24",
            font: { color: "#e8edf6", size: 12 },
            margin: { t: 24, r: 16, b: 48, l: 56 },
            xaxis: { title: "Time (UTC)", gridcolor: "#273043" },
            yaxis: { title: sym, gridcolor: "#273043" },
          },
          { responsive: true, displayModeBar: true },
        );
      }
      if (!silent) logger.info("dashboard", status);
    } catch (e) {
      setStatus("Load failed — see console");
      logger.error("dashboard", "readings failed", e);
    } finally {
      if (!silent) setLoading(false);
    }
  }, [hours, unit, rolling, siteId, buildingId]);

  useEffect(() => {
    void load();
    const id = window.setInterval(() => void load(true), 30000);
    return () => {
      window.clearInterval(id);
      if (chartRef.current) Plotly.purge(chartRef.current);
    };
  }, [load]);

  return (
    <div className="stack-page">
      <TopBar
        title="Dashboard"
        subtitle="BACnet telemetry for selected site/building · DynamoDB · FDD"
      />
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
      <div className="card toolbar-card">
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
        <label>
          Rolling avg (min)
          <select value={rolling} onChange={(e) => setRolling(Number(e.target.value))}>
            {[1, 5, 10, 15].map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </label>
        <button type="button" onClick={() => void load()} disabled={loading}>
          {loading ? "Loading…" : "Refresh"}
        </button>
        <span className="muted">{status}</span>
      </div>
      <div className="card chart-card">
        <div ref={chartRef} className="plot-host" />
      </div>
    </div>
  );
}
