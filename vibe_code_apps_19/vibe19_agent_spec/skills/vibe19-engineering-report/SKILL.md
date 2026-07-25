---
name: vibe19-engineering-report
description: >-
  Build or change the Vibe19 Engineering Findings Report: evidence packets,
  Passes 1–7 reviewer, detection≠finding, clustering ≤7, quality gate, Kaleido
  charts, DOCX+JSON, Overview generate button / HITL, headless CLI, checklist-JSON
  path. Triggers on: engineering findings, evidence review, STRONGLY_SUPPORTED,
  DATA_QUALITY, report DOCX, app/reporting, engineering-report extras.
---

# Vibe19 — Engineering Findings Report

**Brand:** Open FDD Vibe Coder. **Detection ≠ finding.**

This is a **second product** beside the static Generic RCx DOCX. Do not merge them.
Do not invent new FDD rules here. Do not derive compressor runtime from pump status.

## Products (keep separate)

| Product | Path | When |
| --- | --- | --- |
| Generic RCx (static) | `assets/reports/Open-FDD_Generic_RCx_Report_v1.docx` via `app/docx_report.py` | Overview download — bytes only, no python-docx |
| Engineering Findings | `app/reporting/` | Overview **Generate** button or CLI — evidence-reviewed |

## Non-negotiables

1. **Lazy generate** — only on button / CLI. Never rebuild on Overview visit or every Streamlit rerun.
2. **Raw FAULTs stay in appendix** — priority findings are reviewed + clustered (default ≤7).
3. **No new cookbook rules** in this package — review existing detections / checklist rows.
4. **No compressor-from-pump** — respect compressor-proof analytics contract.
5. Optional extras: `pip install '.[engineering-report]'` (`python-docx`, `kaleido`).
6. **Analysis period** — from Overview / dataset span (`format_analysis_period`), not a hardcoded empty string.
7. **Quality gate** — do not flag honesty language (“Do not replace…”); only proactive replace on weak classes.
8. **Day-zoom** — every included finding gets a PNG or an observable skip reason / muted DOCX note.
9. **DOCX visual language** — cover / muted meta / numbered H1 / bold table headers match vibe20 Energy Modeling client DOCX tokens (same family, different product).

## Package map

| Module | Role |
| --- | --- |
| `app/reporting/models.py` | Candidate, EvidencePacket, Finding, classifications |
| `app/reporting/evidence.py` | Build evidence packet from candidate / checklist row |
| `app/reporting/reviewer.py` | Passes 1–7 → score → classification |
| `app/reporting/candidates.py` | RuleResult / checklist JSON → candidates |
| `app/reporting/findings.py` | Cluster, prioritize, peer/common-mode |
| `app/reporting/narrative.py` | Finding prose |
| `app/reporting/quality_gate.py` | Gate before ship (anti-replace aware) |
| `app/reporting/charts.py` | Kaleido chart selection |
| `app/reporting/day_zoom.py` | Peak-fault-day PNG + skip reasons |
| `app/reporting/overview_export.py` | Overview settings/PNGs + `format_analysis_period` |
| `app/reporting/docx.py` | Engineering Findings DOCX (client cover tokens) |
| `app/reporting/pipeline.py` | `build_engineering_findings` / `render_engineering_report` |
| `app/reporting/cli.py` | Headless CLI |
| `app/report_downloads.py` | Overview panel + HITL include/note |
| `app/agent_api.py` | Typed wrappers (`list_candidate_faults`, …) |

## Classifications (score → category)

Typical ladder (see `reviewer.py` / tests): `STRONGLY_SUPPORTED`, `SUPPORTED`, `POSSIBLE`, `DATA_QUALITY`, `INCONCLUSIVE`, suppressed false positives.

Regression smells (generic logic — not hard-coded building IDs):

- ~5°F zone → **DATA_QUALITY**, not comfort finding
- Fan-off duct static ≫ fan-on → strong support when packet proves it
- Damper ≈ 0 with flow ≫ fault_%-only claim
- Near-100% CHW without telemetry proof → not **STRONGLY_SUPPORTED**

## UI

```text
Overview → Reports
  Generic RCx download (unchanged)
  Generate Engineering Findings Report  ← button only
  Engineer review (Include / Note) → download DOCX + JSON
```

Wire: `streamlit_app.py` → `render_engineering_findings_panel(batch_results=…)`.

## Headless CLI

```bash
cd vibe_code_apps_19
.venv/bin/python -m app.reporting.cli \
  --checklist-json /path/to/*_checklist.json \
  --out-dir /path/to/out \
  --docx --json
```

Also: `--dump` WattLab zip/folder + optional `--run-rules`.

Liberty / WattLab workspace bridge: checklist under `reports/controls_checklist/`; findings under `reports/engineering_findings/` (see wattlab `tools/README.md`).

## Tests

```bash
.venv/bin/python -m pytest -q \
  tests/test_report_*.py \
  tests/test_finding_*.py \
  tests/test_false_positive_review.py \
  tests/test_near_continuous_fault_review.py \
  tests/test_peer_common_mode_detection.py
```

Also keep Generic RCx suite green: `tests/test_docx_report.py`.

## Docs to update when changing this feature

- [`docs/PLOTS_DOCX_VALIDATION.md`](../../docs/PLOTS_DOCX_VALIDATION.md)
- [`docs/DASHBOARD_CONTRACT.md`](../../docs/DASHBOARD_CONTRACT.md)
- [`docs/PERF_BOTTLENECKS.md`](../../docs/PERF_BOTTLENECKS.md) (lazy-only)
- [`SESSION_LOG.md`](../../SESSION_LOG.md)
- Root [`AGENTS.md`](../../../AGENTS.md) + this skill
