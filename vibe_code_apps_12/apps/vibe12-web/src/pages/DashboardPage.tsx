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
  count?: number;
  fdd_open?: {
    fdd_status?: string;
    total_flagged?: number;
    rules_run?: number;
    targets_evaluated?: number;
    open_fdd_version?: string;
    fdd_backend?: string;
    eval_log?: string[];
  };
  chart_truncated?: boolean;
};

type HealthPayload = {
  open_fdd_version?: string;
  open_fdd_version_requested?: string;
  fdd_backend?: string;
  numpy_available?: boolean;
  open_fdd_rule_cookbook?: string;
};

type RuleResult = {
  rule_id?: string;
  target_id?: string;
  title?: string;
  point_class?: string;
  external_id?: string;
  equipment_id?: string;
  rows?: number;
  flagged?: number;
  backend?: string;
  debug_prints?: string[];
  numpy_demo?: boolean;
  error?: string;
};

type BrickFddSummary = {
  total_flagged?: number;
  rules_run?: number;
  targets_evaluated?: number;
  open_fdd_version?: string;
  fdd_backend?: string;
  numpy_available?: boolean;
  results?: RuleResult[];
  eval_log?: string[];
};

const HOURS_OPTS = [6, 24, 48, 168];

import { DEMO_HERO_TITLE } from "../lib/openfdd-demo";

const PIPELINE_STEPS = [
  "Raspberry Pi / BACnet test bench",
  "MQTT → AWS IoT Core",
  "IoT Rule → ingest Lambda",
  "DynamoDB time-series",
  "Scheduled FDD Lambda (pip install open-fdd)",
  "Web Lambda + React dashboard",
];

export function DashboardPage() {
  const { theme } = useTheme();
  const { siteId, buildingId } = useSite();
  const chartRef = useRef<HTMLDivElement>(null);
  const [edgeStatus, setEdgeStatus] = useState<EdgeStatusPayload | null>(null);
  const [health, setHealth] = useState<HealthPayload | null>(null);
  const [brickFdd, setBrickFdd] = useState<BrickFddSummary | null>(null);
  const [showChart, setShowChart] = useState(false);
  const [hours, setHours] = useState(24);
  const [unit, setUnit] = useState<"imperial" | "metric">("imperial");
  const [rolling, setRolling] = useState(1);
  const [chartStatus, setChartStatus] = useState("");
  const [telemetryCount, setTelemetryCount] = useState(0);
  const [latest, setLatest] = useState<{ c: string; f: string }>({ c: "—", f: "—" });
  const [fddStatus, setFddStatus] = useState("PENDING");
  const [loadingChart, setLoadingChart] = useState(false);

  const loadHealth = useCallback(async () => {
    const data = await apiFetch<HealthPayload>("/api/health");
    setHealth(data);
  }, []);

  const loadBrickFdd = useCallback(async () => {
    try {
      const data = await apiFetch<BrickFddSummary>(
        `/api/fdd/brick-results/${encodeURIComponent(siteId)}/${encodeURIComponent(buildingId)}`,
      );
      setBrickFdd(data);
    } catch {
      setBrickFdd(null);
    }
  }, [siteId, buildingId]);

  const loadEdge = useCallback(async () => {
    const data = await apiFetch<EdgeStatusPayload>("/api/edge-devices");
    setEdgeStatus(data);
  }, []);

  const loadChart = useCallback(async () => {
    const url =
      `/api/readings?site_id=${encodeURIComponent(siteId)}&building_id=${encodeURIComponent(buildingId)}` +
      `&hours=${hours}&rolling_avg_minutes=${rolling}&temp_unit=${unit}`;
    try {
      const data = await apiFetch<ReadingsResponse>(url);
      const pts = data.readings || [];
      setTelemetryCount(data.count ?? pts.length);
      setFddStatus(data.fdd_open?.fdd_status || "PENDING");
      if (showChart) {
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
      }
    } catch (e) {
      if (showChart) setChartStatus("Chart load failed");
      logger.error("dashboard", "readings failed", e);
    }
  }, [showChart, hours, unit, rolling, siteId, buildingId, theme]);

  useEffect(() => {
    void loadHealth().catch((e) => logger.error("dashboard", "health", e));
    void loadEdge().catch((e) => logger.error("dashboard", "edge", e));
    void loadBrickFdd().catch((e) => logger.error("dashboard", "brick-fdd", e));
    const id = window.setInterval(() => {
      void loadEdge();
      void loadBrickFdd();
    }, 60000);
    return () => window.clearInterval(id);
  }, [loadHealth, loadEdge, loadBrickFdd]);

  useEffect(() => {
    setLoadingChart(true);
    void loadChart().finally(() => setLoadingChart(false));
    if (!showChart) return;
    const id = window.setInterval(() => void loadChart(), 30000);
    return () => {
      window.clearInterval(id);
      if (chartRef.current) Plotly.purge(chartRef.current);
    };
  }, [loadChart, showChart]);

  const openFddVersion = health?.open_fdd_version || brickFdd?.open_fdd_version || "—";
  const fddBackend = health?.fdd_backend || brickFdd?.fdd_backend || "arrow";
  const numpyOk = health?.numpy_available ?? brickFdd?.numpy_available;
  const totalFlagged = brickFdd?.total_flagged ?? 0;
  const ruleResults = brickFdd?.results || [];

  return (
    <div className="stack-page">
      <TopBar
        title={DEMO_HERO_TITLE}
        subtitle="Pi / BACnet test bench → AWS IoT Core → DynamoDB → Open-FDD PyPI Lambda rules"
      />

      <div className="card hero-card">
        <div className="metric-row">
          <div className="metric-card-inline">
            <span className="muted">open-fdd</span>
            <strong className="mono">{openFddVersion}</strong>
          </div>
          <div className="metric-card-inline">
            <span className="muted">FDD backend</span>
            <strong>{fddBackend}</strong>
          </div>
          <div className="metric-card-inline">
            <span className="muted">NumPy</span>
            <strong>{numpyOk == null ? "—" : numpyOk ? "available" : "unavailable"}</strong>
          </div>
          <div className="metric-card-inline">
            <span className="muted">Site / building</span>
            <strong>
              {siteId} / {buildingId}
            </strong>
          </div>
        </div>
        {health?.open_fdd_rule_cookbook ? (
          <p className="muted small">
            Rule cookbook:{" "}
            <a href={health.open_fdd_rule_cookbook} target="_blank" rel="noreferrer">
              Open-FDD docs
            </a>
          </p>
        ) : null}
      </div>

      <div className="card">
        <h3 className="title">Cloud pipeline</h3>
        <ol className="pipeline-steps">
          {PIPELINE_STEPS.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
        <p className="muted small mono">vibe12/&#123;site&#125;/&#123;building&#125;/&#123;system&#125;/&#123;point&#125;/telemetry</p>
      </div>

      <div className="metric-row">
        <div className="card metric-card">
          <div className="muted">Telemetry samples</div>
          <div className="metric-val">{telemetryCount}</div>
        </div>
        <div className="card metric-card">
          <div className="muted">FDD status</div>
          <div className={`metric-val fdd-chip fdd-${fddStatus}`}>{fddStatus}</div>
        </div>
        <div className="card metric-card">
          <div className="muted">Total flagged</div>
          <div className="metric-val">{totalFlagged}</div>
        </div>
        <div className="card metric-card">
          <div className="muted">Rules / targets</div>
          <div className="metric-val">
            {brickFdd?.rules_run ?? "—"} / {brickFdd?.targets_evaluated ?? "—"}
          </div>
        </div>
      </div>

      {ruleResults.length > 0 ? (
        <div className="card">
          <h3 className="title">Rule results (scheduled FDD)</h3>
          <div className="rule-result-grid">
            {ruleResults.map((r, i) => (
              <div key={`${r.rule_id}-${r.target_id}-${i}`} className="rule-result-card">
                <div className="rule-result-head">
                  <strong>{r.title || r.rule_id}</strong>
                  {r.numpy_demo ? <span className="numpy-badge">NumPy demo</span> : null}
                </div>
                <div className="muted small">
                  {r.point_class} · {r.external_id || r.equipment_id}
                </div>
                <div className="small">
                  rows {r.rows ?? 0} · flagged {r.flagged ?? 0} · {r.backend || "arrow"}
                </div>
                {(r.debug_prints || []).slice(0, 2).map((line) => (
                  <div key={line} className="mono small muted">
                    {line}
                  </div>
                ))}
                {r.error ? <div className="warn-text small">{r.error}</div> : null}
              </div>
            ))}
          </div>
        </div>
      ) : null}

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
          </div>
          <div className="card chart-card">
            <div ref={chartRef} className="plot-host" />
          </div>
        </>
      ) : null}
    </div>
  );
}
