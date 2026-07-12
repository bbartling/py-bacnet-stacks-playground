# Plots + DOCX validation cards

**Audience:** agents editing Plots, Data Model, or FDD Word exports.

**Contract freeze:** [`DASHBOARD_CONTRACT.md`](DASHBOARD_CONTRACT.md) · `app/dashboard_contract.py` (`build_rule_card`, DOCX entrypoints).

**Per-rule chart catalog (Haystack / sliders / series):** [`RULE_PLOT_CATALOG.md`](RULE_PLOT_CATALOG.md).

---

## Purpose

Plots is the **review/validation** surface for the 50-rule cookbook on one device — not a Niagara-style BAS mimic. Each applicable rule is a **card** so an engineer can scan description, tune params, and required vs mapped points before looking at a Plotly figure or pasting into Word.

---

## Key modules

| Path | Role |
| --- | --- |
| `app/rule_card.py` | `build_rule_card`, `equipment_mapping_coverage`, `PLACE_PLOT_HERE` |
| `app/docx_report.py` | `build_equipment_fdd_docx` (card mirror), data-model + analytics DOCX |
| `app/data_model_tree.py` | Equipment → role → Haystack tag → CSV inventory |
| `app/charts.py` | `rule_result_chart` (downsample via `VIBE19_MAX_PLOT_POINTS`) |
| `streamlit_app.py` | **Plots** + **Data Model** + **Export** sections |

---

## Plots UX (required behavior)

1. Device type → device picker.
2. Header: **mapping coverage %**, rule-card count, one-click **Download FDD DOCX**.
3. Filter chips: All / FAULT / PASS / SKIPPED / Not run (default **All**).
4. **One expander (or bordered card) per applicable cookbook rule** — including SKIPPED / N/A / not-run. Sensor-sweep rules count as one card each.
5. Every card always shows: equation/description, tune-param table, required vs mapped points (missing highlighted).
6. **Plotly is lazy** — Streamlit expander bodies always run, so only render `rule_result_chart` for the rule selected in **Plot focus** (one live chart). Do not draw all FAULT charts at once (SIGSEGV risk on low-RAM hosts).
7. Keep economizer / FC6 data-gap caption.

## DOCX UX (required behavior)

`build_equipment_fdd_docx` must literally mirror cards:

- Cover: building, equipment, type, mapping coverage %, generated time
- One section per applicable rule (same order as UI)
- Always include params + mapping tables (even when blank/missing)
- Always insert: **`[PLACE PLOT HERE — paste Plotly PNG from Streamlit camera or Trends]`** unless an optional PNG is passed
- Optional analytics appendix (motor weekly / cool bins tables) — no embedded kaleido for all 50 rules in v1

Export tab: prominent **Download equipment FDD DOCX** for the selected device + data_model / analytics downloads.

**Do not** restore a “Build DOCX” then separate “Download” two-step dance.

---

## Agent checklist

- [ ] `app.rule_card:build_rule_card` still in `REQUIRED_UI_ENTRYPOINTS`
- [ ] Plots source contains card catalog (`Filter cards` / rule validation cards) + `Download FDD DOCX`
- [ ] DOCX unzip XML contains `PLACE PLOT HERE` + a rule id + a role/param
- [ ] `python -m pytest -q tests/test_rule_card.py tests/test_docx_report.py tests/test_rcx_presets.py`
