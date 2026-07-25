# Occupied-Standby+DCV, Client DOCX UX, and Eng Findings Hardening — Design

**Date:** 2026-07-25  
**Status:** Approved — implementing  
**Apps:** vibe19 (FDD Engineering Findings) + vibe20 (WattLab Studio ECMs)  
**Approved product choice:** New catalog measure `ECM-OCC-STANDBY-DCV` (keep `ECM-DCV-CO2`)

---

## 1. Goal

Ship one coherent client-facing ECM + FDD deliverable story:

1. **vibe20** — Add Occupied-Standby + Demand-Controlled Ventilation as a first-class ECM; rank Easy Buttons easy→hard; richer AI scenario defaults; surface ESCO spreadsheet math in UI + package; add a **selectable client DOCX** beside MD/XLSX/ZIP.
2. **vibe19** — Fix Eng Findings BUG-016/017/018; restyle the FDD Engineering Findings DOCX so its cover, section rhythm, tables, and muted captions feel like the vibe20 ECM client DOCX (same family, different product).
3. **Docs / specs** — Update `ecm_library`, `docs`, `vibe20_agent_spec`, and `vibe19_agent_spec` so agents and humans share one source of truth.
4. **Ship** — Unit tests, green GH Actions, CodeRabbit on PR, tidy stale branches, merge `develop`, refresh GHCR turnkey images.

---

## 2. Non-goals

- No parallel ECM registry (`catalog.yaml` remains canonical; `ecm_library` stays a shim).
- Do not invent new vibe19 FDD cookbook rules for this effort.
- Do not merge Generic RCx static DOCX with Engineering Findings.
- Do not conflate controls-checklist DOCX with the new WattLab **energy/ECM client DOCX**.
- No PE-signed report claims; honesty stamps stay mandatory on vibe20 packages.
- No force-push / destructive git ops; no committing secrets.

---

## 3. Shared client DOCX visual language

Both products keep distinct titles and content, but share presentation tokens so a client reading an FDD findings pack and an ECM energy pack recognizes the same OpenFDD / WattLab family.

| Token | Spec |
| --- | --- |
| Cover title | Centered Heading 0; product-specific string |
| Subtitle / site | Centered bold ~16 pt building or project name |
| Meta line | Muted gray (~`#4A5568`) 10 pt: period · generated timestamp |
| Advisory callout | Italic 10 pt disclaimer paragraph under meta (not a floating badge) |
| Section rhythm | Numbered `N. Title` Heading 1; optional Heading 2 for indexes / measure cards |
| Tables | `Table Grid`; header row bold; compact body; no card chrome |
| Captions | Same muted helper as meta for chart / day-zoom / skip notes |
| Page breaks | Cover → body; optional break before appendices |
| Brand voice | “Open-FDD advisory…” (vibe19) / “WattLab screening — not CD/TAB…” (vibe20) |

**Implementation approach:** Prefer a small shared styling helper *per app* (not a cross-repo package):

- vibe19: extend `app/reporting/docx.py` helpers (`_muted`, add `_cover`, `_section_h1`, `_style_table_header`).
- vibe20: new `wattlab/deliverables_docx.py` (or `wattlab/reporting/client_docx.py`) that mirrors those helpers and maps the existing 14-section executive markdown outline into DOCX.

Optional later: extract a tiny shared module only if duplication becomes painful — out of scope unless both land in the same PR and copy-paste exceeds ~80 lines of identical helpers.

**UI parity (Studio / Streamlit):**

- vibe19 Eng Findings panel already has generate + downloads; keep checkbox semantics for optional media.
- vibe20 ECMs / Twin “Build client package” gains **Include client DOCX** checkbox (default on when `python-docx` available; soft-skip + caption if missing).
- Both download rows show DOCX beside MD/XLSX/ZIP where applicable.

---

## 4. vibe19 — Engineering Findings hardening

### 4.1 BUG-016 — Day-zoom skip reasons

**Today:** `attach_day_zoom_to_findings` silently `continue`s; DOCX `_add_finding_picture` returns with no note.

**Target:**

- Return / record skip metas with `skip_reason ∈ {excluded, no_result, no_fault_day, render_failed}`.
- Set `EngineeringFinding.day_zoom_skip_reason` (and optional `day_zoom_label` note) when PNG missing.
- DOCX: if no day-zoom/chart PNG, emit muted line: `Day-zoom unavailable: <reason>`.
- Charts JSON audit list includes skip metas (not only successes).

### 4.2 BUG-017 — Quality gate anti-replace false positive

**Today:** substring `"replace"` flags default corrective *“Do not replace equipment solely…”*.

**Target:** Gate only proactive replace recommendations (e.g. recommend replacing equipment/sensor) on weak classifications. Phrases matching `do not replace` / `don't replace` / `never replace` are ignored. Keep rejecting weak-class *“replace the … sensor/equipment”* without STRONGLY/PROBABLE.

Optionally leave `_corrective` wording unchanged (gate fix is sufficient).

### 4.3 BUG-018 — Analysis period from dataset window

**Today:** `streamlit_app.py` passes `analysis_period=""`; cover shows “see assumptions” while Overview settings already have start/end/span.

**Target:** Derive `YYYY-MM-DD → YYYY-MM-DD (~N h)` from `overview_context` / `dataset_start`+`dataset_end`+`span_hours` inside `build_engineering_findings` (and CLI when context exists). Stop hardcoding empty string in Streamlit (pass through or omit).

### 4.4 Eng Findings DOCX UX (new — user request)

Restyle `app/reporting/docx.py` to match §3 tokens and vibe20 ECM client DOCX structure:

| Section | Behavior |
| --- | --- |
| Cover | Shared cover helper; real analysis period; advisory italic |
| 1. Executive summary | Metrics paragraph + **Priority index** table with styled header |
| 2. Building at a glance | Overview settings + Kaleido overview PNGs + summary charts |
| 3. Prioritized findings | Finding cards as H2; status badge line; evidence bullets; day-zoom or skip note |
| 4–7 + Appendices | Keep content; apply same table header + muted caption helpers |

Do **not** change detection≠finding semantics, clustering ≤7, or Passes 1–7.

### 4.5 vibe19_agent_spec updates

| File | Update |
| --- | --- |
| `SESSION_LOG.md` | Top entry: BUG-016/017/018 + DOCX UX alignment with vibe20 client package |
| `skills/vibe19-engineering-report/SKILL.md` | Package map (`day_zoom`, `overview_export`); gate anti-replace rule; period from span; shared DOCX visual language |
| `docs/PLOTS_DOCX_VALIDATION.md` | Day-zoom + skip note; cover period; style checklist vs vibe20 ECM DOCX |
| Optional | `docs/DASHBOARD_CONTRACT.md` one-liner if Overview→report period contract needs it |

### 4.6 vibe19 tests

- `test_report_day_zoom.py` — skip reasons
- `test_report_docx.py` — skip muted note; styled cover period; priority table present
- `test_report_quality_gate.py` — anti-replace OK; proactive replace fails on INCONCLUSIVE
- `test_report_overview_export.py` / CLI overview tests — period derivation
- Keep `validate_eng_findings_docx_media.py` green (media ≥2 when Kaleido/matplotlib available)

---

## 5. vibe20 — Occupied-Standby + DCV and client package

### 5.1 New measure `ECM-OCC-STANDBY-DCV`

**Catalog** (`wattlab/measures/catalog.yaml`):

| Field | Value |
| --- | --- |
| `ecm_id` | `ECM-OCC-STANDBY-DCV` |
| `display_name` | Occupied-standby + demand-controlled ventilation |
| `category` | `oa_ventilation` |
| `implementation_complexity` | `medium` (standby scheduling low; DCV medium → composite medium) |
| `proxy_calculator` | Prefer a named composite or document dual dispatch in Studio proxies |
| `dependencies` | Include sensor / schedule prerequisites as appropriate (align with `ECM-DCV-CO2`) |
| `iaq_risk` | `high` |
| `status` | `PRODUCTION_PROXY_ONLY` initially |
| `energyplus_patch` | `null` until a real IDF patch exists |

**Proxy wiring** (`wattlab/studio/proxies.py`):

- Match `OCC-STANDBY` / `OCC_STANDBY` / id contains both standby+DCV intent.
- Combine existing ESCO calculators: `oad_unoccupied_closed` + `dcv_bins` (sum electric/thermal with clear provenance in result dict).
- Keep `ECM-DCV-CO2` → `dcv_bins` only.
- Wire ROI seed in `ecm_roi.py` (`DEFAULT_ECM_ROI_MODELS`) with a documented $/ft² band.

**Packages:**

- Add to `esco-top15` near other OA/ventilation measures (after DCV or as adjacent rank — document exact slot in coverage matrix).
- Consider `low-cost` / `controls-only` / `no-capital-rcx` membership where engineering-appropriate.
- Incompatibilities: respect existing zero-OA vs occupied DCV rules; document in `ECM_INTERACTIONS.md`.

### 5.2 Rank Easy Buttons easy → hard

- Sort catalog cards by `implementation_complexity` rank (`low`→`medium`→`high`), then category, then `ecm_id`.
- Show complexity caption on each card (e.g. “Complexity: medium”).
- Do **not** reorder `ESCO_TOP15` screening rank semantics; that tuple remains ESCO screening order. UI default presentation uses complexity; package order still follows `resolve_package`.

### 5.3 Richer AI agent defaults (`ecm_scenario.json`)

Extend schema **compatibly** (version bump to `2` if needed; v1 loaders still accept missing keys):

```json
{
  "version": 2,
  "selected_ecm_ids": ["ECM-AHU-SCHED-ALIGN", "ECM-OCC-STANDBY-DCV", "..."],
  "measure_set": null,
  "sort_preference": "implementation_complexity",
  "package_hints": ["esco-top15"],
  "proxy_defaults": {},
  "roi_param_hints": {},
  "notes": "",
  "recommendations": [],
  "status": "..."
}
```

- Agent tools / `CONTAINER_AGENT.md` / `AGENT_DOCKER_WORKSPACE.md` examples use **real** `ECM-*` ids (fix stale `fan_schedule_optimization` examples).
- Studio `_ensure_checkbox_defaults` still seeds checkboxes from `selected_ecm_ids`; optionally honor `sort_preference`.

### 5.4 ESCO spreadsheet calcs in UI + report

- Keep human doc `docs/ESCO_SPREADSHEET_CALCS.md` as formula map; add Occupied-Standby+DCV row (OAD unocc closed + DCV bins).
- Studio ECMs page: ensure crosscheck / proxy columns expose calculator names for the new measure.
- Client MD **and** DOCX section 9 (ECMs) list measure id, proxy calculator provenance, kWh/therms when present.
- Agent spec `ESCO_CALCULATORS.md` + skill `wattlab-esco-bins` mention composite measure.

### 5.5 Selectable client DOCX deliverable

- New renderer maps `build_executive_markdown` 14-section outline → DOCX using §3 visual language.
- `package_deliverables(..., include_docx: bool = False)` writes `01_Report/Energy_Modeling_Report.docx` when requested.
- Studio checkbox on ECMs + Twin calibrate package builders.
- CLI flag if a package CLI exists; otherwise document Studio-only first.
- **Separate** from `controls_checklist.render_docx`.

### 5.6 `ecm_library`

- Keep shim to `wattlab.measures`.
- Add `ecm_library/README.md` stating deprecation + pointer to `catalog.yaml` and Occupied-Standby+DCV id.
- Fix stale `CONTENTS.md` references to `ecm_library/measure_sets.json`.

### 5.7 vibe20 `docs/` updates

| Doc | Update |
| --- | --- |
| `README.md` | Link new measure + client DOCX |
| `ESCO_SPREADSHEET_CALCS.md` | OCC-STANDBY-DCV formulas + paths |
| `ECM_EASY_BUTTONS.md` | Complexity sort; full package list incl. `esco-top15`; new measure |
| `ecm_coverage_matrix.md` | New row + package membership |
| `ECM_CALCULATION_METHODS.md` | Composite proxy |
| `ECM_INTERACTIONS.md` | Incompat / stacking notes |
| This design + plan under `docs/superpowers/` | As written |

### 5.8 `vibe20_agent_spec` updates

| File | Update |
| --- | --- |
| `docs/AGENT_TOOLS.md` | Scenario v2 fields; package DOCX |
| `docs/ESCO_CALCULATORS.md` | Composite calculators |
| `docs/CALIBRATE_AND_DELIVERABLES.md` | Client DOCX checkbox + path |
| `docs/AGENT_DOCKER_WORKSPACE.md` | Real ECM ids in examples |
| `CONTAINER_AGENT.md` | Scenario write + DOCX deliverable |
| `AGENTS.md` | Pointers if needed |
| Skills: `wattlab-studio`, `wattlab-esco-bins`, `wattlab-assumptions` | Ranking, defaults, DOCX, new ECM |
| Add / append SESSION-style note if the tree has a session log; else CONTAINER_AGENT changelog section |

### 5.9 vibe20 tests

- Catalog: new id loads; package resolve; incompat
- Proxies: OCC-STANDBY-DCV combines oad + dcv; DCV alone unchanged
- Easy Buttons sort helper unit test
- `ecm_scenario` v2 load/save backward compatible
- Deliverables: `include_docx=True` produces DOCX bytes; checkbox path doesn’t break ZIP
- Golden ESCO: existing `oad_unoccupied_closed` / `dcv_bins` remain; optional composite golden

---

## 6. Ship / ops (both apps)

| Step | Detail |
| --- | --- |
| Branches | Feature branches from `develop`; prefer two PRs (vibe19 then vibe20) or one stacked PR if tightly coupled on DOCX tokens |
| Tests | App-local pytest suites for touched modules; keep turnkey/Docker smokes green |
| CI | Green GitHub Actions required before merge |
| CodeRabbit | Address review comments before merge |
| Branch tidy | Close/delete merged remotes: `feat/vibe19-fdd-overview-day-zoom`, `fix/vibe19-eng-findings-bugs-011-015`, kaleido/dockerfile branches if already merged |
| GHCR | Path-filter publish; vibe19 refresh after merge; vibe20 when paths fire; `workflow_dispatch` `no_cache=true` if `:latest` sticky |
| Turnkey verify | Pull recreate; vibe19 `:8502` Eng Findings DOCX media + period; vibe20 `:8520` ECM card + client DOCX |

---

## 7. Phased delivery (recommended)

| Phase | Scope | Independently shippable? |
| --- | --- | --- |
| **P1** | vibe19 BUG-016/017/018 + Eng Findings DOCX UX + vibe19_agent_spec | Yes |
| **P2** | vibe20 `ECM-OCC-STANDBY-DCV` + proxy + packages + complexity sort + scenario v2 | Yes |
| **P3** | vibe20 client DOCX + Studio checkbox + deliverables tests | Yes (after P2 preferred so ECM section has content) |
| **P4** | Docs/`ecm_library`/vibe20_agent_spec sweep + ESCO doc rows | Can land with P2/P3 |
| **P5** | PR review, merge, GH tidy, GHCR, turnkey QA | After green CI |

Shared DOCX visual language: implement helpers in P1 (vibe19), mirror in P3 (vibe20) so styles converge.

---

## 8. Success criteria

- Eng Findings DOCX: non-empty analysis period when Overview span exists; day-zoom or explicit skip note per included finding; quality gate accepts “Do not replace…”; cover/sections match §3.
- Studio ECMs: new measure visible, complexity-sorted, proxy savings non-zero on synthetic bins; agent scenario can pre-select it with real ids.
- Client package ZIP optionally contains Energy Modeling DOCX with numbered sections and honesty disclaimer.
- Spec/docs folders listed in §4.5 / §5.6–5.8 updated; `ecm_library` README clarifies shim.
- CI green; CodeRabbit resolved; turnkey containers refreshed and smoke-checked.

---

## 9. Open items (resolve during implementation, not blockers)

1. Exact `esco-top15` rank slot for `ECM-OCC-STANDBY-DCV` (adjacent to `ECM-DCV-CO2` recommended).
2. Whether composite proxy is a new `@register` calculator vs Studio-only sum of two registered calcs (prefer Studio sum + documented provenance to avoid double-counting in golden registry — or a thin registered wrapper that calls both).
3. Default for “Include client DOCX” checkbox (recommend **on** when dependency present).

---

## 10. Spec self-review

- [x] No TBD placeholders for core behavior
- [x] vibe19 + vibe20 + all four requested doc surfaces included
- [x] User DOCX UX alignment request included
- [x] Non-goals prevent registry / product conflation
- [x] Phases keep shippable slices
- [x] Tests and ops called out
