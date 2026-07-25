# Occupied-Standby+DCV, Complexity Rank, Agent Defaults, Client DOCX — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `ECM-OCC-STANDBY-DCV`, rank Studio ECMs easy→hard, enrich `ecm_scenario` defaults, surface ESCO math, ship selectable client DOCX styled like vibe19 Eng Findings, and update `ecm_library` / `docs` / `vibe20_agent_spec`.

**Architecture:** Canonical measure in `catalog.yaml`; Studio proxies compose `oad_unoccupied_closed` + `dcv_bins`; Easy Buttons sort by `implementation_complexity`; `deliverables_docx` mirrors executive MD into python-docx; docs/agent_spec stay in lockstep.

**Tech Stack:** Python, YAML catalog, Streamlit Studio, ESCO bin calcs, python-docx, pytest.

**Design:** [`../specs/2026-07-25-occ-standby-dcv-eng-findings-hardening-design.md`](../specs/2026-07-25-occ-standby-dcv-eng-findings-hardening-design.md) §3, §5–6.

**Depends on (soft):** vibe19 plan Task 4 DOCX tokens for visual parity — [`vibe_code_apps_19/.../2026-07-25-eng-findings-hardening-docx-ux.md`](../../../vibe_code_apps_19/docs/superpowers/plans/2026-07-25-eng-findings-hardening-docx-ux.md).

## Global Constraints

- No parallel ECM registry — `wattlab/measures/catalog.yaml` only; `ecm_library` remains a shim.
- Do not conflate client Energy Modeling DOCX with `controls_checklist` DOCX.
- Honesty stamps / G14 / area scale remain mandatory in packages.
- `ESCO_TOP15` screening order semantics stay; UI presentation sorts by complexity separately.
- Real `ECM-*` ids in all agent examples.
- YAGNI: no EnergyPlus patch until a real IDF exists (`PRODUCTION_PROXY_ONLY`).

## File map

| File | Role |
| --- | --- |
| `wattlab/measures/catalog.yaml` | New measure |
| `wattlab/ecm/packages.py` | Package membership / esco-top15 slot |
| `wattlab/studio/proxies.py` | Composite proxy dispatch |
| `wattlab/studio/ecm_roi.py` | ROI seed |
| `wattlab/studio/pages/ecm_easy_buttons.py` | Complexity sort + caption |
| `wattlab/studio/ecm_scenario.py` + template | Schema v2 |
| `wattlab/deliverables.py` | `include_docx` flag |
| `wattlab/deliverables_docx.py` (new) | Client DOCX renderer |
| `wattlab/studio/pages/ecms.py` / twin package UI | Checkbox |
| `ecm_library/README.md` | Shim documentation |
| `docs/*` | ESCO, Easy Buttons, coverage, methods, interactions, README |
| `vibe20_agent_spec/*` | Tools, ESCO, deliverables, container, skills |
| `tests/test_ecm_*.py`, `test_deliverables*.py`, `test_esco_golden.py` | Coverage |

---

### Task 1: Catalog measure `ECM-OCC-STANDBY-DCV`

**Files:**
- Modify: `wattlab/measures/catalog.yaml`
- Modify: `wattlab/ecm/packages.py` (membership)
- Test: `tests/test_ecm_catalog.py`

**Interfaces:**
- Produces: `get_ecm("ECM-OCC-STANDBY-DCV")` with complexity `medium`, category `oa_ventilation`, `PRODUCTION_PROXY_ONLY`
- Package: insert in `ESCO_TOP15` adjacent to `ECM-DCV-CO2`; add to applicable packages

- [ ] **Step 1: Failing test** — catalog contains id; `resolve_package("esco-top15")` includes it; deps resolve
- [ ] **Step 2: Add YAML entry** (deps/incompat aligned with `ECM-DCV-CO2` / existing OA rules)
- [ ] **Step 3: Update `PACKAGES` / `ESCO_TOP15`**
- [ ] **Step 4: Tests green**
- [ ] **Step 5: Commit** `feat(vibe20): add ECM-OCC-STANDBY-DCV to catalog and packages`

---

### Task 2: Proxy composite + ROI seed

**Files:**
- Modify: `wattlab/studio/proxies.py`
- Modify: `wattlab/studio/ecm_roi.py`
- Test: new or extend `tests/test_ecm_roi.py` + proxy unit test (create `tests/test_studio_proxies_occ_standby.py` if none)

**Interfaces:**
- Consumes: `oad_unoccupied_closed`, `dcv_bins` from `wattlab.bench.esco`
- Produces: proxy dict with summed savings + `calculators: ["oad_unoccupied_closed", "dcv_bins"]` provenance
- `ECM-DCV-CO2` path unchanged (dcv only)

- [ ] **Step 1: Failing tests** for composite vs DCV-only
- [ ] **Step 2: Dispatch in `estimate_proxy_savings`**
- [ ] **Step 3: ROI default $/ft² for new id**
- [ ] **Step 4: Tests green**
- [ ] **Step 5: Commit** `feat(vibe20): wire OCC-STANDBY-DCV proxy to OAD-unocc + DCV bins`

---

### Task 3: Easy Buttons complexity sort

**Files:**
- Modify: `wattlab/studio/pages/ecm_easy_buttons.py`
- Optional helper: `wattlab/ecm/ranking.py` with `complexity_sort_key`
- Test: unit test for sort key / ordered ids

**Interfaces:**
- Produces: UI order low→medium→high; caption shows complexity
- Does not mutate `ESCO_TOP15` tuple meaning

- [ ] **Step 1: Failing test** for sort order across mixed complexities
- [ ] **Step 2: Implement sort + caption**
- [ ] **Step 3: Tests green**
- [ ] **Step 4: Commit** `feat(vibe20): rank ECM Easy Buttons by implementation complexity`

---

### Task 4: Agent scenario schema v2

**Files:**
- Modify: `wattlab/studio/ecm_scenario.py`
- Modify: `wattlab/studio/templates/ecm_scenario.template.json`
- Test: `tests/test_live_08_status_fixes.py`, `tests/test_studio_status_deliverables.py`

**Interfaces:**
- Produces: v2 fields (`sort_preference`, `package_hints`, `proxy_defaults`, `roi_param_hints`) with backward-compatible load of v1 files

- [ ] **Step 1: Failing tests** — load v1 file still works; save v2 round-trips new keys
- [ ] **Step 2: Implement empty/load/save**
- [ ] **Step 3: Easy Buttons honor `sort_preference` when present**
- [ ] **Step 4: Tests green**
- [ ] **Step 5: Commit** `feat(vibe20): enrich ecm_scenario.json agent defaults (v2)`

---

### Task 5: Client DOCX deliverable (vibe20 ECM / energy package)

**Files:**
- Create: `wattlab/deliverables_docx.py`
- Modify: `wattlab/deliverables.py` (`package_deliverables(..., include_docx: bool = False)`)
- Modify: `wattlab/studio/pages/ecms.py` (+ twin package UI if separate)
- Test: `tests/test_studio_status_deliverables.py` / `tests/test_deliverables_campaign.py`

**Interfaces:**
- Produces: `01_Report/Energy_Modeling_Report.docx` using design §3 tokens (mirror vibe19 helpers)
- Consumes: same inputs as `build_executive_markdown` (scorecard, report, profile, savings)
- Separate from `controls_checklist.render_docx`

- [ ] **Step 1: Failing test** — `include_docx=True` writes DOCX; zip contains it; `include_docx=False` omits
- [ ] **Step 2: Implement `render_energy_modeling_docx`** — 14 sections, muted meta, styled tables, honesty italic
- [ ] **Step 3: Wire `package_deliverables` + Studio checkbox “Include client DOCX”**
- [ ] **Step 4: Soft-skip with caption if python-docx missing**
- [ ] **Step 5: Tests green**
- [ ] **Step 6: Commit** `feat(vibe20): selectable client Energy Modeling DOCX in deliverables`

---

### Task 6: Docs + ecm_library + vibe20_agent_spec

**Files:**
- Create: `ecm_library/README.md`
- Modify: `CONTENTS.md` (stale measure_sets path) if present at app root
- Modify: `docs/README.md`, `docs/ESCO_SPREADSHEET_CALCS.md`, `docs/ECM_EASY_BUTTONS.md`, `docs/ecm_coverage_matrix.md`, `docs/ECM_CALCULATION_METHODS.md`, `docs/ECM_INTERACTIONS.md`
- Modify: `vibe20_agent_spec/docs/AGENT_TOOLS.md`, `ESCO_CALCULATORS.md`, `CALIBRATE_AND_DELIVERABLES.md`, `AGENT_DOCKER_WORKSPACE.md`
- Modify: `vibe20_agent_spec/CONTAINER_AGENT.md`, `AGENTS.md` as needed
- Modify: skills `wattlab-studio`, `wattlab-esco-bins`, `wattlab-assumptions`

- [ ] **Step 1: ecm_library README** — shim only; point to catalog + `ECM-OCC-STANDBY-DCV`
- [ ] **Step 2: ESCO + Easy Buttons + coverage + methods + interactions**
- [ ] **Step 3: Agent spec + skills** — scenario v2, DOCX path, real ECM ids, composite calc
- [ ] **Step 4: Commit** `docs(vibe20): OCC-STANDBY-DCV, complexity rank, client DOCX, agent defaults`

---

### Task 7: Verify + PR + ops

- [ ] **Step 1: Run** catalog, proxy, ROI, deliverables, esco golden, scenario tests
- [ ] **Step 2: PR to `develop`; address CodeRabbit**
- [ ] **Step 3: Tidy merged remote branches** listed in design §6 (after confirming merged)
- [ ] **Step 4: GHCR vibe20 refresh when path-filter fires; turnkey `:8520` smoke** — new ECM visible, complexity order, DOCX in package when checked

---

## Cross-cutting checklist (do not skip)

- [ ] Design open item: confirm `esco-top15` slot next to DCV
- [ ] Design open item: Studio-sum vs registered composite calculator (prefer Studio sum + provenance unless golden registry needs a name)
- [ ] Design open item: DOCX checkbox default **on** when python-docx present
- [ ] Visual parity spot-check: open vibe19 Eng Findings DOCX and vibe20 Energy Modeling DOCX side-by-side (cover, muted meta, H1 numbering, table headers)
- [ ] No stale agent example ids remain in `AGENT_DOCKER_WORKSPACE.md` / `CONTAINER_AGENT.md`
