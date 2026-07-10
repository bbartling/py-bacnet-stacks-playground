# Operational gates + SKIPPED_EQUIPMENT_OFF — Implementation Plan

> **For agentic workers:** Implement task-by-task. Checkboxes track progress. Pandas/Streamlit App 19 only (no DataFusion in this repo).

**Goal:** Gate most of the 50 cookbook rules behind equipment-specific operational proof (fan/pump/compressor/flow/occupied), add `SKIPPED_EQUIPMENT_OFF`, expose a default-on UI toggle, and surface sensor-fault summary stats on Plots/exports.

**Architecture:** Registry-level `RULE_GATES` map (ALWAYS / RUN / CONDITIONAL) + shared `resolve_operational_mask()` applied in `runner.py` before confirm/finalize. Prefer status/proof roles over `fan_cmd`. Global + per-rule “require operational proof” checkbox (default on for RUN).

**Tech Stack:** pandas, Streamlit, pytest, existing `RuleResult` contract.

**Default branch:** `develop` (no open PRs to merge).

---

## File map

| File | Responsibility |
| --- | --- |
| `app/rules/operational_gate.py` | Gate kinds, role priority, running mask, startup delay |
| `app/rules/base.py` | Add `SKIPPED_EQUIPMENT_OFF` + factory |
| `app/rules/runner.py` | Apply gate; skip when inactive; active-sample denominator |
| `app/analytics.py` | Sensor fault summary stats for Plots/Export |
| `streamlit_app.py` | Global gate checkbox; Plots sensor stats; Results metric |
| `vibe19_agent_spec/` | Spec + SESSION_LOG + pandas-fdd skill |
| `tests/test_operational_gate.py` | Unit + runner integration |

---

### Task 1: Spec + gate module (TDD)

- [ ] Write `vibe19_agent_spec/docs/OPERATIONAL_GATES.md` (this design)
- [ ] Failing tests for fan_status > fan_cmd priority, SKIPPED_EQUIPMENT_OFF, ALWAYS rules ungated
- [ ] Implement `operational_gate.py` + `RULE_GATES` for all 50 IDs (PID-HUNT-1 replaces SV-4 as RUN/control)

### Task 2: Runner + status contract

- [ ] Extend `RuleStatus` / `equipment_off()`
- [ ] Wire runner: if gate required and active coverage &lt; min → `SKIPPED_EQUIPMENT_OFF`; else `raw &= active`
- [ ] `fault_pct` / hours use active samples as denominator when gated

### Task 3: UI

- [ ] Sidebar checkbox **Require operational proof** (default checked)
- [ ] Per-rule param `require_operational_gate` (0/1) + `startup_delay_min` for RUN rules
- [ ] Results tab metric for EQUIPMENT_OFF
- [ ] Plots: sensor fault summary table + CSV export helper

### Task 4: Validate, commit, push develop

- [ ] `pytest -q` + AppTest clean
- [ ] Commit all App 19 work; push `origin/develop`
- [ ] Confirm no open PRs/branches left

---

## Gate classification (App 19 IDs)

**ALWAYS (8):** SV-RANGE, SV-SPIKE, SV-STALE, WX-1, WX-2, OAT-METEO, SCHED-1, CMD-1

**CONDITIONAL (4):** SV-FLATLINE, DMP-1, VAV-1, VLV-1

**RUN (~38):** all FC*, AHU-*, ECON-*, OA-1, VAV-3/4/5/7/REHEAT, CHW-*, HP-1, TRIM-*, PID-HUNT-1

Proof priority (fan): `fan_status` → `fan_speed_feedback` → `fan_current` → `airflow_proof` → `fan_cmd` fallback.

Hydronic: `pump_status` / `chw_flow` / `pump_cmd` fallback.
