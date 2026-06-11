import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiFetch } from "../lib/api-client";
import { logger } from "../lib/logger";
import {
  buildRuleLabLlmBundle,
  copyText,
  downloadJson,
  formatRuleTestEvents,
  type RuleTestEvent,
} from "../lib/rule-lab-console";
import { useSite } from "../contexts/site-context";
import { TopBar } from "../components/layout/TopBar";
import { PythonCodeEditor } from "../components/PythonCodeEditor";
import { ARROW_RULE_CONTRACT } from "../lib/openfdd-demo";

type FddRule = {
  id: string;
  title: string;
  enabled?: boolean;
  color?: string;
  code?: string;
  config?: Record<string, unknown>;
  brick_scope?: Record<string, unknown>;
};

type RulesPayload = {
  rules: FddRule[];
  rules_source?: string;
  brick_scope_options?: { equipment: string[]; points: string[]; has_data?: boolean };
};

type BrickScopeTest = {
  targets_evaluated?: number;
  total_flagged?: number;
  ms?: number;
  results?: Array<{
    target_id?: string;
    equipment_type?: string;
    point_class?: string;
    flagged?: number;
    rows?: number;
  }>;
};

function scopeSummary(scope?: Record<string, unknown>): string {
  if (!scope) return "All points on building (no BRICK filter — uses dashboard ZAT series for quick test)";
  const pts = (scope.point_classes as string[]) || [];
  const eq = (scope.equipment_classes as string[]) || [];
  if (!pts.length && !eq.length) return "No BRICK classes selected";
  const parts: string[] = [];
  if (pts.length) parts.push(`points: ${pts.join(", ")}`);
  if (eq.length) parts.push(`equipment: ${eq.join(", ")}`);
  return parts.join(" · ");
}

export function RuleLabPage() {
  const { siteId, buildingId } = useSite();
  const [rules, setRules] = useState<FddRule[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [source, setSource] = useState("");
  const [consoleOut, setConsoleOut] = useState("");
  const [testSummary, setTestSummary] = useState("");
  const [brickScopeNote, setBrickScopeNote] = useState("");
  const [testHours, setTestHours] = useState(2);
  const [editingTitle, setEditingTitle] = useState(false);
  const [editingScope, setEditingScope] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const [brickEq, setBrickEq] = useState<string[]>([]);
  const [brickPt, setBrickPt] = useState<string[]>([]);
  const [scopeOpts, setScopeOpts] = useState<{ equipment: string[]; points: string[] }>({
    equipment: [],
    points: [],
  });
  const [copyHint, setCopyHint] = useState("");

  const selected = rules.find((r) => r.id === selectedId) || rules[0];

  const loadRules = useCallback(async () => {
    const data = await apiFetch<RulesPayload>(
      `/api/fdd-rules?site_id=${encodeURIComponent(siteId)}&building_id=${encodeURIComponent(buildingId)}&temp_unit=imperial`,
    );
    const list = (data.rules || []).map((r) => JSON.parse(JSON.stringify(r)) as FddRule);
    setRules(list);
    setSource(data.rules_source || "");
    setScopeOpts(data.brick_scope_options || { equipment: [], points: [] });
    if (!selectedId && list[0]) setSelectedId(list[0].id);
    logger.info("rulelab", `loaded ${list.length} rules`);
  }, [siteId, buildingId, selectedId]);

  useEffect(() => {
    void loadRules().catch((e) => logger.error("rulelab", "load failed", e));
  }, [loadRules]);

  useEffect(() => {
    if (!selected) return;
    setTitleDraft(selected.title || selected.id);
    setEditingTitle(false);
    setEditingScope(false);
    const scope = selected.brick_scope as { equipment_classes?: string[]; point_classes?: string[] };
    setBrickEq(scope?.equipment_classes || []);
    setBrickPt(scope?.point_classes || []);
  }, [selected?.id]);

  const llmBundle = useMemo(() => {
    if (!selected) return "";
    return buildRuleLabLlmBundle({
      siteId,
      buildingId,
      rule: selected,
      testSummary: testSummary || "(run Test rule)",
      consoleBody: consoleOut,
      brickScopeNote: brickScopeNote || scopeSummary(selected.brick_scope),
    });
  }, [selected, siteId, buildingId, testSummary, consoleOut, brickScopeNote]);

  function updateSelected(patch: Partial<FddRule>) {
    if (!selected) return;
    setRules((prev) => prev.map((r) => (r.id === selected.id ? { ...r, ...patch } : r)));
  }

  function applyBrickScope() {
    if (!selected) return;
    if (!brickEq.length && !brickPt.length) {
      updateSelected({ brick_scope: undefined });
      return;
    }
    const scope: Record<string, unknown> = {};
    if (brickPt.length) scope.point_classes = brickPt;
    if (brickEq.length) scope.equipment_classes = brickEq;
    scope.match_mode = brickPt.length && !brickEq.length ? "point_only" : "all_points_on_equipment";
    updateSelected({ brick_scope: scope });
  }

  async function saveRules() {
    applyBrickScope();
    const res = await apiFetch<{ count: number }>("/api/fdd-rules", {
      method: "POST",
      body: JSON.stringify({ rules }),
    });
    setConsoleOut((prev) => `Saved ${res.count} rule(s) to DynamoDB (draft slot, ts_ms=-2).\n\n${prev}`);
    logger.info("rulelab", "rules saved");
    await loadRules();
  }

  async function testRule() {
    if (!selected) return;
    applyBrickScope();
    const rule = { ...selected, brick_scope: selected.brick_scope };

    const res = await apiFetch<{
      flagged: number;
      rows: number;
      ms: number;
      events?: RuleTestEvent[];
    }>("/api/playground/test-rule", {
      method: "POST",
      body: JSON.stringify({
        rule,
        hours: testHours,
        verbose: true,
        site_id: siteId,
        building_id: buildingId,
      }),
    });

    const summary = `Test (single series): ${res.rows} rows, ${res.flagged} flagged, ${res.ms} ms`;
    setTestSummary(summary);

    const eventText = formatRuleTestEvents(res.events || []);
    let body = `${summary}\n\n${eventText}\n`;

    const scope = rule.brick_scope as { point_classes?: string[]; equipment_classes?: string[] } | undefined;
    const hasScope =
      scope &&
      ((scope.point_classes?.length ?? 0) > 0 || (scope.equipment_classes?.length ?? 0) > 0);

    if (hasScope) {
      try {
        const brick = await apiFetch<BrickScopeTest>("/api/playground/test-brick-rule", {
          method: "POST",
          body: JSON.stringify({
            rule,
            site_id: siteId,
            building_id: buildingId,
            hours: testHours,
          }),
        });
        const lines = (brick.results || []).map(
          (r) =>
            `  ${r.target_id} · ${r.equipment_type || "?"}/${r.point_class || "?"} · flagged ${r.flagged}/${r.rows}`,
        );
        const brickSummary = `BRICK scope test: ${brick.targets_evaluated ?? 0} sensor target(s), ${brick.total_flagged ?? 0} total flags, ${brick.ms ?? 0} ms`;
        setBrickScopeNote(`${scopeSummary(scope)}\n${lines.join("\n") || "(no targets matched model)"}`);
        body += `\n--- ${brickSummary} ---\n${lines.join("\n")}\n`;
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        body += `\nBRICK scope test failed: ${msg}\n`;
        setBrickScopeNote(`Scope test error: ${msg}`);
      }
    } else {
      setBrickScopeNote(
        "Quick test uses one dashboard temperature series. Set BRICK point/equipment classes below (✎) then re-test to validate all matching sensors.",
      );
    }

    setConsoleOut(body);
    logger.info("rulelab", `test ${selected.id}`, { flagged: res.flagged });
  }

  async function goLive() {
    applyBrickScope();
    const res = await apiFetch<{ summary?: { chunk_count?: number }; hours?: number }>(
      "/api/playground/go-live",
      {
        method: "POST",
        body: JSON.stringify({ rules, site_id: siteId, building_id: buildingId }),
      },
    );
    setConsoleOut(
      `Write to database — go-live backfill complete.\n` +
        `Chunks: ${res.summary?.chunk_count ?? "?"}, lookback: ${res.hours ?? "?"} h\n` +
        `BRICK-scoped rules in this list are evaluated per sensor in the canonical model.\n`,
    );
    logger.info("rulelab", "go-live complete");
  }

  function exportRulesJson() {
    downloadJson(`fdd-rules-${siteId}-${buildingId}.json`, { rules, site_id: siteId, building_id: buildingId });
  }

  async function copyForLlm() {
    const ok = await copyText(llmBundle);
    setCopyHint(ok ? "Copied for LLM." : "Copy failed — select console text.");
    setTimeout(() => setCopyHint(""), 2500);
  }

  return (
    <div className="stack-page">
      <TopBar
        title="Arrow Rule Lab"
        subtitle={`Open-FDD PyPI · ${ARROW_RULE_CONTRACT} · test against DynamoDB telemetry`}
      />
      <div className="card toolbar-card">
        <label>
          Rule
          <select value={selected?.id || ""} onChange={(e) => setSelectedId(e.target.value)}>
            {rules.map((r) => (
              <option key={r.id} value={r.id}>
                {r.title || r.id}
                {r.enabled === false ? " (off)" : ""}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="secondary-btn"
          onClick={() => {
            const id = `custom_rule_${Date.now().toString(36)}`;
            const r: FddRule = {
              id,
              title: "New rule",
              enabled: true,
              color: "#58a6ff",
              code: "def apply_faults_arrow(table, cfg, context=None):\n    import pyarrow as pa\n    return pa.array([False] * len(table))\n",
              config: {},
            };
            setRules((p) => [...p, r]);
            setSelectedId(id);
          }}
        >
          + Add
        </button>
        <label>
          Test window (h)
          <input
            type="number"
            min={1}
            max={168}
            value={testHours}
            onChange={(e) => setTestHours(Number(e.target.value))}
          />
        </label>
        <button type="button" onClick={() => void testRule()}>
          Test rule
        </button>
        <button type="button" className="secondary-btn" onClick={() => void saveRules()} title="Persist rules to DynamoDB draft (ts_ms=-2)">
          Save rules
        </button>
        <button
          type="button"
          onClick={() => void goLive()}
          title="Backfill FDD flags to database; BRICK-scoped rules run on every matching sensor"
        >
          Write to database
        </button>
        <button type="button" className="secondary-btn" onClick={exportRulesJson}>
          Export JSON
        </button>
        <span className="muted">Source: {source || "—"}</span>
      </div>
      {selected ? (
        <div className="card">
          <div className="rule-name-row">
            {editingTitle ? (
              <>
                <input value={titleDraft} onChange={(e) => setTitleDraft(e.target.value)} />
                <button
                  type="button"
                  onClick={() => {
                    updateSelected({ title: titleDraft.trim() || selected.id });
                    setEditingTitle(false);
                  }}
                >
                  Done
                </button>
                <button type="button" className="secondary-btn" onClick={() => setEditingTitle(false)}>
                  Cancel
                </button>
              </>
            ) : (
              <>
                <strong>{selected.title || selected.id}</strong>
                <button
                  type="button"
                  className="secondary-btn"
                  onClick={() => setEditingTitle(true)}
                  title="Rename rule"
                >
                  ✎
                </button>
              </>
            )}
          </div>

          <div className="brick-scope-block">
            <div className="rule-name-row">
              <span className="muted">BRICK apply scope (go-live + scope test)</span>
              <button
                type="button"
                className="secondary-btn"
                onClick={() => setEditingScope((v) => !v)}
                title="Edit which sensors this rule targets"
              >
                ✎
              </button>
              <Link to="/data-model" className="muted small-link">
                Data model →
              </Link>
            </div>
            <p className="scope-summary-text">{scopeSummary(selected.brick_scope)}</p>
            {editingScope && (scopeOpts.points.length > 0 || scopeOpts.equipment.length > 0) ? (
              <div className="grid-two">
                <label>
                  Point classes (BRICK)
                  <select
                    multiple
                    size={5}
                    value={brickPt}
                    onChange={(e) => setBrickPt([...e.target.selectedOptions].map((o) => o.value))}
                  >
                    {scopeOpts.points.map((c) => (
                      <option key={c} value={c}>
                        {c.replace(/_/g, " ")}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Equipment types
                  <select
                    multiple
                    size={5}
                    value={brickEq}
                    onChange={(e) => setBrickEq([...e.target.selectedOptions].map((o) => o.value))}
                  >
                    {scopeOpts.equipment.map((c) => (
                      <option key={c} value={c}>
                        {c.replace(/_/g, " ")}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            ) : null}
            {editingScope ? (
              <button
                type="button"
                className="secondary-btn"
                onClick={() => {
                  applyBrickScope();
                  setEditingScope(false);
                }}
              >
                Apply scope to rule
              </button>
            ) : null}
            {!scopeOpts.points.length && !scopeOpts.equipment.length ? (
              <p className="muted">
                Ingest telemetry and sync the{" "}
                <Link to="/data-model">data model</Link> to pick BRICK classes.
              </p>
            ) : null}
          </div>

          <PythonCodeEditor
            value={selected.code || ""}
            height="260px"
            onChange={(v) => updateSelected({ code: v })}
          />
        </div>
      ) : null}
      <div className="card console-card">
        <div className="console-header">
          <h3 className="title">Console</h3>
          <div className="console-actions">
            <button type="button" className="secondary-btn" onClick={() => void copyForLlm()}>
              Copy for LLM
            </button>
            {copyHint ? <span className="muted">{copyHint}</span> : null}
          </div>
        </div>
        <p className="muted console-hint">
          Contract: <code>apply_faults_arrow(table, cfg, context=None)</code>. Maintained recipes:{" "}
          <a href="https://bbartling.github.io/open-fdd/rule-cookbook/" target="_blank" rel="noreferrer">
            Open-FDD rule cookbook
          </a>
          . Save rules → DynamoDB draft; Write to database → go-live backfill + BRICK-scoped evaluation.
        </p>
        <pre className="console-pre">{consoleOut || "Run Test rule to see print() output and scope results."}</pre>
      </div>
    </div>
  );
}
