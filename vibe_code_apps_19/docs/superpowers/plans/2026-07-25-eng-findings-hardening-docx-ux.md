# vibe19 Eng Findings Hardening + DOCX UX — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix BUG-016/017/018 and restyle the FDD Engineering Findings DOCX to share cover/section/table/caption language with the vibe20 ECM client package.

**Architecture:** Harden day-zoom + quality gate + analysis_period in `app/reporting/`; restyle `docx.py` helpers to a shared visual token set documented in the design spec; update `vibe19_agent_spec`.

**Tech Stack:** Python, pytest, python-docx, matplotlib (day-zoom), Plotly/Kaleido (overview), Streamlit.

**Design:** [`vibe_code_apps_20/docs/superpowers/specs/2026-07-25-occ-standby-dcv-eng-findings-hardening-design.md`](../../../vibe_code_apps_20/docs/superpowers/specs/2026-07-25-occ-standby-dcv-eng-findings-hardening-design.md) §3–4.

## Global Constraints

- Detection ≠ finding; do not add cookbook rules.
- Do not merge Generic RCx static DOCX with Engineering Findings.
- Kaleido/Chromium path already fixed (BUG-011); do not regress.
- Anti-replace narrative must remain in default corrective text; fix the gate, not by deleting honesty language.
- Follow existing test patterns in `tests/test_report_*.py`.

## File map

| File | Role |
| --- | --- |
| `app/reporting/day_zoom.py` | Skip reasons + metas |
| `app/reporting/models.py` | `day_zoom_skip_reason` field |
| `app/reporting/docx.py` | Cover/section helpers + skip note + UX |
| `app/reporting/quality_gate.py` | Proactive-replace detection |
| `app/reporting/pipeline.py` / `overview_export.py` | Format + fill `analysis_period` |
| `streamlit_app.py` | Stop hardcoding `analysis_period=""` |
| `app/reporting/cli.py` | Same period derivation when context exists |
| `vibe19_agent_spec/*` | SESSION_LOG, engineering-report skill, PLOTS_DOCX_VALIDATION |
| `tests/test_report_{day_zoom,docx,quality_gate,overview_export}.py` | Regressions |

---

### Task 1: BUG-017 quality gate anti-replace

**Files:**
- Modify: `app/reporting/quality_gate.py`
- Test: `tests/test_report_quality_gate.py`

**Interfaces:**
- Produces: `run_quality_gate` ignores `do not replace` / `don't replace` / `never replace`; still errors on weak-class proactive replace.

- [ ] **Step 1: Write failing tests**

```python
def test_quality_gate_allows_do_not_replace_on_inconclusive():
    # finding with possible_corrective containing "Do not replace equipment solely..."
    # classification INCONCLUSIVE → gate ok

def test_quality_gate_rejects_proactive_replace_on_inconclusive():
    # possible_corrective = ["Replace the outdoor-air damper actuator"]
    # → errors mention replace
```

- [ ] **Step 2: Run tests — expect fail**
- [ ] **Step 3: Implement proactive-replace helper** (regex or negation phrases + require replace + equipment/sensor/actuator language)
- [ ] **Step 4: Run tests — expect pass**
- [ ] **Step 5: Commit** `fix(vibe19): ignore anti-replace wording in Eng Findings quality gate`

---

### Task 2: BUG-018 analysis_period from overview span

**Files:**
- Modify: `app/reporting/overview_export.py` (add `format_analysis_period`)
- Modify: `app/reporting/pipeline.py`
- Modify: `streamlit_app.py` (~2827)
- Modify: `app/reporting/cli.py` if needed
- Test: `tests/test_report_overview_export.py`, optionally CLI test

**Interfaces:**
- Produces: `format_analysis_period(ctx) -> str` like `2024-01-01 → 2024-03-31 (~2160 h)`
- Consumes: `overview_context` keys `dataset_start`, `dataset_end`, `span_hours`

- [ ] **Step 1: Failing test** for `format_analysis_period` + pipeline fill when caller passes `""`
- [ ] **Step 2: Implement helper + pipeline fallback**
- [ ] **Step 3: Streamlit — pass formatted period from `_ov_ctx` or omit and let pipeline fill**
- [ ] **Step 4: Tests green**
- [ ] **Step 5: Commit** `fix(vibe19): fill Eng Findings analysis_period from dataset window`

---

### Task 3: BUG-016 day-zoom skip reasons + DOCX note

**Files:**
- Modify: `app/reporting/models.py`
- Modify: `app/reporting/day_zoom.py`
- Modify: `app/reporting/docx.py` (`_add_finding_picture`)
- Modify: `app/reporting/charts.py` if needed to keep skip metas
- Test: `tests/test_report_day_zoom.py`, `tests/test_report_docx.py`

**Interfaces:**
- Produces: `day_zoom_skip_reason` on finding; metas with `skip_reason`; DOCX muted note

- [ ] **Step 1: Failing tests** for `no_result` / `no_fault_day` skip metas and DOCX XML containing `Day-zoom unavailable`
- [ ] **Step 2: Implement attach_day_zoom skip recording**
- [ ] **Step 3: DOCX muted note when no picture**
- [ ] **Step 4: Tests green**
- [ ] **Step 5: Commit** `fix(vibe19): record day-zoom skip reasons in Eng Findings DOCX`

---

### Task 4: Eng Findings DOCX UX aligned with vibe20 client tokens

**Files:**
- Modify: `app/reporting/docx.py`
- Test: `tests/test_report_docx.py`

**Interfaces:**
- Produces: `_cover`, `_section_h1`, `_style_table_header` (names flexible) matching design §3

- [ ] **Step 1: Snapshot/assert helpers** — cover title centered; muted meta; priority table header bold; advisory italic present
- [ ] **Step 2: Refactor `render_docx` to use helpers** without changing section inventory
- [ ] **Step 3: Ensure day-zoom skip note + analysis period still present**
- [ ] **Step 4: Tests green**
- [ ] **Step 5: Commit** `feat(vibe19): align Eng Findings DOCX cover/sections with WattLab client style`

---

### Task 5: vibe19_agent_spec

**Files:**
- Modify: `vibe19_agent_spec/SESSION_LOG.md`
- Modify: `vibe19_agent_spec/skills/vibe19-engineering-report/SKILL.md`
- Modify: `vibe19_agent_spec/docs/PLOTS_DOCX_VALIDATION.md`

- [ ] **Step 1: SESSION_LOG top entry** for BUG-016/017/018 + DOCX UX
- [ ] **Step 2: Skill package map + non-negotiables** (period, gate, skip notes, style tokens)
- [ ] **Step 3: PLOTS_DOCX_VALIDATION checklist** update
- [ ] **Step 4: Commit** `docs(vibe19): agent_spec notes for Eng Findings hardening`

---

### Task 6: Verify + PR

- [ ] **Step 1: Run** `pytest tests/test_report_day_zoom.py tests/test_report_docx.py tests/test_report_quality_gate.py tests/test_report_overview_export.py` (and related)
- [ ] **Step 2: Optional** `scripts/validate_eng_findings_docx_media.py` in Docker if available
- [ ] **Step 3: Open PR to `develop`; address CodeRabbit**
- [ ] **Step 4: After merge — GHCR vibe19 refresh + turnkey smoke on `:8502`**

---

## Parallel plan

vibe20 work: [`2026-07-25-occ-standby-dcv-client-docx.md`](../../../vibe_code_apps_20/docs/superpowers/plans/2026-07-25-occ-standby-dcv-client-docx.md) (may start after Task 4 helpers exist so DOCX tokens can be mirrored).
