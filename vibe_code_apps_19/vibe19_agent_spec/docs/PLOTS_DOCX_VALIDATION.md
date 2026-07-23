# Plots + Generic RCx DOCX validation

**Audience:** agents editing FDD Plots, Data Model, or the Generic RCx Word report.

**Contract freeze:** [`DASHBOARD_CONTRACT.md`](DASHBOARD_CONTRACT.md) · `app/dashboard_contract.py` (`build_rule_card`, `load_generic_rcx_report`, Overview download).

**Per-rule chart catalog (Haystack / sliders / series):** [`RULE_PLOT_CATALOG.md`](RULE_PLOT_CATALOG.md).

---

## Purpose

**FDD Plots** is the **review/validation** surface for the cookbook on one device — not a Niagara-style BAS mimic. Each applicable rule is a **card** so an engineer can scan **Summary** + **Equation**, tune params, and required vs mapped points before looking at a Plotly figure.

Word narrative lives in one committed Generic RCx template (not generated per device).

---

## Key modules

| Path | Role |
| --- | --- |
| `app/rule_card.py` | `build_rule_card`, `equipment_mapping_coverage`, `PLACE_PLOT_HERE` stubs for validation docs |
| `app/docx_report.py` | Serve `Open-FDD_Generic_RCx_Report_v1.docx` from `assets/reports/` — **no python-docx** |
| `app/report_downloads.py` | Overview primary download button |
| `app/data_model_tree.py` | Equipment → role → Haystack tag → CSV inventory (+ feeds/fedBy) |
| `app/charts.py` | `rule_result_chart`, `bas_vs_web_oat_histogram`, … |
| `streamlit_app.py` | **FDD Plots** (charts/cards) + **Overview** (Generic RCx DOCX) + **Data Model** + **Metering** + **Export** |

---

## FDD Plots UX (required behavior)

1. Device type → device picker.
2. **Auto-run** applicable rules for the selected device when that device has no evaluations yet (manual **Re-run device rules** still available).
3. Device strip: history row count, time span, mapped-role count, **mapping coverage %**.
4. Downloads on Plots: **session_config.json**, **role_map.json** (Word report is on **Overview** only).
5. **Chart panel on top** — selectbox picks one rule; always render that rule’s Plotly (never default to “tables only / none”). Prefer first FAULT after a run.
6. Filter chips: All / FAULT / PASS / SKIPPED / Not run (default **All**).
7. **One expander per applicable cookbook rule** below the chart — catalog parity with [`RULE_PLOT_CATALOG.md`](RULE_PLOT_CATALOG.md).
8. **One live Plotly only** (low-RAM). Cap points with `VIBE19_MAX_PLOT_POINTS`.
9. Keep economizer / FC6 data-gap caption.

Shared builder: `app.rule_card:build_rule_card` (+ `app.rule_plot_meta`).

## DOCX UX (required behavior)

**Product 1 — Generic RCx (unchanged):**

Exactly **one** committed static template:

- `assets/reports/Open-FDD_Generic_RCx_Report_v1.docx`
- Primary download on **Overview** via `render_overview_rcx_download`
- No per-equipment FDD DOCX, no family RCx DOCX pack, no Export ZIP pack
- Engineers customize by replacing the file in place (same filename)
- Served as bytes only — **no** python-docx on this path

**Product 2 — Engineering Findings Report (deliberate addition):**

- Generated from active rule FAULTs / checklist JSON via `app/reporting/`
- Overview: **Generate Engineering Findings Report** button only (never on section visit)
- Optional extras: `pip install '.[engineering-report]'` (`python-docx`, `kaleido`)
- Headless: `python -m app.reporting.cli --checklist-json … --out-dir … --docx --json`
- Contract: detection ≠ finding; raw hits in appendix; ≤7 priority findings
- Skill: [`../skills/vibe19-engineering-report/SKILL.md`](../skills/vibe19-engineering-report/SKILL.md)

Do **not** commit generated Engineering Findings DOCX under `assets/reports/`.

---

## Agent checklist

- [ ] `app.rule_card:build_rule_card` and `app.docx_report:load_generic_rcx_report` still in `REQUIRED_UI_ENTRYPOINTS`
- [ ] Plots source contains card catalog (`Filter cards` / rule validation cards)
- [ ] Overview contains Generic RCx download; FDD/RCx/Export do not serve other DOCX paths
- [ ] `python -m pytest -q tests/test_rule_card.py tests/test_docx_report.py tests/test_rcx_presets.py`
