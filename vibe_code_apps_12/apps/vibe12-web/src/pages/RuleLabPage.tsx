import CodeMirror from "@uiw/react-codemirror";
import { python } from "@codemirror/lang-python";
import { oneDark } from "@codemirror/theme-one-dark";
import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../lib/api-client";
import { logger } from "../lib/logger";
import { useSite } from "../contexts/site-context";
import { TopBar } from "../components/layout/TopBar";

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

export function RuleLabPage() {
  const { siteId, buildingId } = useSite();
  const [rules, setRules] = useState<FddRule[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [source, setSource] = useState("");
  const [consoleOut, setConsoleOut] = useState("");
  const [testHours, setTestHours] = useState(2);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const [brickEq, setBrickEq] = useState<string[]>([]);
  const [brickPt, setBrickPt] = useState<string[]>([]);
  const [scopeOpts, setScopeOpts] = useState<{ equipment: string[]; points: string[] }>({
    equipment: [],
    points: [],
  });

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
    const scope = selected.brick_scope as { equipment_classes?: string[]; point_classes?: string[] };
    setBrickEq(scope?.equipment_classes || []);
    setBrickPt(scope?.point_classes || []);
  }, [selected?.id]);

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

  async function saveDraft() {
    const res = await apiFetch<{ count: number }>("/api/fdd-rules", {
      method: "POST",
      body: JSON.stringify({ rules }),
    });
    setConsoleOut(`Draft saved (${res.count} rules).\n`);
    logger.info("rulelab", "draft saved");
    await loadRules();
  }

  async function testRule() {
    if (!selected) return;
    applyBrickScope();
    const res = await apiFetch<{ flagged: number; rows: number; ms: number; events?: string[] }>(
      "/api/playground/test-rule",
      {
        method: "POST",
        body: JSON.stringify({
          rule: selected,
          hours: testHours,
          verbose: true,
          site_id: siteId,
          building_id: buildingId,
        }),
      },
    );
    const lines = [
      `Test: ${res.rows} rows, ${res.flagged} flagged, ${res.ms} ms`,
      ...(res.events || []).slice(0, 40),
    ];
    setConsoleOut(lines.join("\n") + "\n");
    logger.info("rulelab", `test ${selected.id}`, { flagged: res.flagged });
  }

  async function goLive() {
    const res = await apiFetch<{ summary?: { chunk_count?: number }; hours?: number }>(
      "/api/playground/go-live",
      {
        method: "POST",
        body: JSON.stringify({ rules, site_id: siteId, building_id: buildingId }),
      },
    );
    setConsoleOut(
      `Go live done — chunks ${res.summary?.chunk_count ?? "?"}, lookback ${res.hours ?? "?"} h\n`,
    );
    logger.info("rulelab", "go-live complete");
  }

  return (
    <div className="stack-page">
      <TopBar title="Rule Lab" subtitle="Bake-a-Py custom rules · draft in DynamoDB · go-live backfill" />
      <div className="card toolbar-card">
        <label>
          Rule
          <select
            value={selected?.id || ""}
            onChange={(e) => setSelectedId(e.target.value)}
          >
            {rules.map((r) => (
              <option key={r.id} value={r.id}>
                {r.title || r.id}
                {r.enabled === false ? " (off)" : ""}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="secondary-btn" onClick={() => {
          const id = `custom_rule_${Date.now().toString(36)}`;
          const r: FddRule = { id, title: "New rule", enabled: true, color: "#58a6ff", code: "def evaluate(row, cfg, prev_row=None, rows=None):\n    return False\n", config: {} };
          setRules((p) => [...p, r]);
          setSelectedId(id);
        }}>
          + Add
        </button>
        <label>
          Test window (h)
          <input type="number" min={1} max={168} value={testHours} onChange={(e) => setTestHours(Number(e.target.value))} />
        </label>
        <button type="button" onClick={() => void testRule()}>Test rule</button>
        <button type="button" className="secondary-btn" onClick={() => void saveDraft()}>Save draft</button>
        <button type="button" onClick={() => void goLive()}>Write to database</button>
        <span className="muted">Source: {source || "—"}</span>
      </div>
      {selected ? (
        <div className="card">
          <div className="rule-name-row">
            {editingTitle ? (
              <>
                <input value={titleDraft} onChange={(e) => setTitleDraft(e.target.value)} />
                <button type="button" onClick={() => {
                  updateSelected({ title: titleDraft.trim() || selected.id });
                  setEditingTitle(false);
                }}>Done</button>
                <button type="button" className="secondary-btn" onClick={() => setEditingTitle(false)}>Cancel</button>
              </>
            ) : (
              <>
                <strong>{selected.title || selected.id}</strong>
                <button type="button" className="secondary-btn" onClick={() => setEditingTitle(true)} title="Rename">✎</button>
              </>
            )}
          </div>
          {(scopeOpts.points.length > 0 || scopeOpts.equipment.length > 0) ? (
            <div className="brick-scope-block">
              <p className="muted">BRICK targets (from registry / model)</p>
              <div className="grid-two">
                <label>
                  Point classes
                  <select
                    multiple
                    size={4}
                    value={brickPt}
                    onChange={(e) => setBrickPt([...e.target.selectedOptions].map((o) => o.value))}
                  >
                    {scopeOpts.points.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Equipment types
                  <select
                    multiple
                    size={4}
                    value={brickEq}
                    onChange={(e) => setBrickEq([...e.target.selectedOptions].map((o) => o.value))}
                  >
                    {scopeOpts.equipment.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </label>
              </div>
            </div>
          ) : (
            <p className="muted">No BRICK classes in registry yet for this site/building.</p>
          )}
          <CodeMirror
            value={selected.code || ""}
            height="220px"
            theme={oneDark}
            extensions={[python()]}
            onChange={(v) => updateSelected({ code: v })}
          />
        </div>
      ) : null}
      <div className="card">
        <h3 className="title">Console</h3>
        <pre className="console-pre">{consoleOut || "Test or save to see output."}</pre>
      </div>
    </div>
  );
}
