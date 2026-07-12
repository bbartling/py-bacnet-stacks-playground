# Plots + DOCX validation cards

**Audience:** agents editing Plots, Data Model, or FDD Word exports.

**Contract freeze:** [`DASHBOARD_CONTRACT.md`](DASHBOARD_CONTRACT.md) · `app/dashboard_contract.py` (`build_rule_card`, DOCX entrypoints).

**Per-rule chart catalog (Haystack / sliders / series):** [`RULE_PLOT_CATALOG.md`](RULE_PLOT_CATALOG.md).

---

## Purpose

Plots is the **review/validation** surface for the cookbook on one device — not a Niagara-style BAS mimic. Each applicable rule is a **card** so an engineer can scan **Summary** (one sentence) + **Equation**, tune params, and required vs mapped points before looking at a Plotly figure or pasting into Word.

---

## Key modules

| Path | Role |
| --- | --- |
| `app/rule_card.py` | `build_rule_card`, `equipment_mapping_coverage`, `PLACE_PLOT_HERE` |
| `app/docx_report.py` | `build_equipment_fdd_docx` (Plots template: description + equation + plot stub), data-model / RCx / analytics DOCX |
| `app/data_model_tree.py` | Equipment → role → Haystack tag → CSV inventory (+ feeds/fedBy) |
| `app/charts.py` | `rule_result_chart`, `bas_vs_web_oat_histogram`, … |
| `streamlit_app.py` | **Plots** (FDD DOCX) + **Data Model** + **Metering** + **Export** |

---

## Plots UX (required behavior)

1. Device type → device picker.
2. **Auto-run** applicable rules for the selected device when that device has no evaluations yet (manual **Re-run device rules** still available).
3. Device strip: history row count, time span, mapped-role count, **mapping coverage %**.
4. Downloads on Plots: **session_config.json**, **role_map.json**, one-click **Download FDD DOCX**.
5. **Chart panel on top** — selectbox picks one rule; always render that rule’s Plotly (never default to “tables only / none”). Prefer first FAULT after a run.
6. Filter chips: All / FAULT / PASS / SKIPPED / Not run (default **All**).
7. **One expander per applicable cookbook rule** below the chart — **catalog parity** with [`RULE_PLOT_CATALOG.md`](RULE_PLOT_CATALOG.md):
   - **Summary** (one sentence from `CookbookRule.summary`)
   - Equation
   - Rule facts (family, equipment kinds, operational gate, default confirm, sweep)
   - Points → Haystack (+ live CSV column / in-history)
   - Plot series bullets
   - Sliders with Value / Default / Min / Max / Step
   - Analytics / related + live data-model fit lines
8. **One live Plotly only** (low-RAM). Cap points with `VIBE19_MAX_PLOT_POINTS`. Do not draw all FAULT charts at once.
9. Keep economizer / FC6 data-gap caption.

Shared builder: `app.rule_card:build_rule_card` (+ `app.rule_plot_meta`).

## DOCX UX (required behavior)

`build_equipment_fdd_docx` is a **dummy engineer template** (not a full card dump):

- Key findings placeholder
- Per applicable rule: **Description** (`CookbookRule.summary`) + **Equation** + **`[PLACE PLOT HERE]`**

No analytics tables, mapping grids, or slider dumps in the FDD Word file.

`build_rcx_catalog_docx` (RCx Plots + Export): building cover, family-grouped catalog for all 50 rules, analytics/RCx coverage filled when fit, **`[PLACE RCX PLOT HERE — {preset_id}]`** stubs.

---

## Agent checklist

- [ ] `app.rule_card:build_rule_card` still in `REQUIRED_UI_ENTRYPOINTS`
- [ ] Plots source contains card catalog (`Filter cards` / rule validation cards) + `Download FDD DOCX`
- [ ] DOCX unzip XML contains `PLACE PLOT HERE` + a rule id + a role/param
- [ ] `python -m pytest -q tests/test_rule_card.py tests/test_docx_report.py tests/test_rcx_presets.py`
