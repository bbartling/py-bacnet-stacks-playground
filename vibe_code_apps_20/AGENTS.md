# AGENTS.md — Vibe App 20 / Sketchbox (agent OS)

**Single entrypoint for agents.** Prefer this file over scattered notes. Domain skills under `.agents/skills/` remain the procedure detail; routing is `.agents/routing.md`.

## Mission

Build a safe, auditable bridge from Open-FDD / Vibe App 19 analytics to conceptual Sketchbox ECM screening. Optimize for engineering defensibility, reproducibility, and graceful recovery from UI changes.

Sketchbox has **no public API**. Playwright UI automation is best-effort scaffolding only.

### Conceptual disclaimer (required on anonymized / uncalibrated exports)

> This is a conceptual, uncalibrated screening model for an anonymized office building. It is not a design load calculation, code-compliance model, calibrated energy model, or representation of a specific Madison property.

## Mandatory reading order

1. This file (`AGENTS.md`)
2. `.agents/routing.md`
3. `.agents/policies.md`
4. `.agents/data_contract.md`
5. The selected skill’s `SKILL.md`
6. The applicable checklist under `.agents/checklists/`

Prefer **current UI behavior + this handbook** over any stale lesson notes.

## Hard rules

- Never commit `.env`, passwords, cookies, tokens, session storage, downloaded project archives, or customer data.
- Never claim Sketchbox has a public API.
- Never use browser selectors as the only record of a modeled input.
- Never overwrite an existing project without a saved export or explicit human approval.
- Never convert a fault directly into savings without a causal chain and applicability gate.
- Never bundle interacting ECMs while reporting them as independent savings.
- Never silently change a blue/default-derived Sketchbox value; record whether it was accepted, refreshed, or overridden.
- Never represent a specialized HVAC system as an exact match when Sketchbox only supports an approximation.
- Never publish utility savings or payback without listing rate, escalation, cost, and confidence assumptions.
- Never expose the actual building location in reports when the project is marked anonymized.
- Missing evidence produces `NEEDS_INPUT`, not invented values.
- UI automation failure must leave the project recoverable and produce artifacts explaining the last confirmed state.
- Full ASHRAE Guideline 36 sequences are **not** available as a Sketchbox button — only labeled proxies (`conceptual_gl36_proxy`).

## Standard statuses

`READY` · `NEEDS_INPUT` · `NEEDS_ENGINEERING_REVIEW` · `BLOCKED_UI_CHANGE` · `BLOCKED_AUTH` · `MODEL_RUN_FAILED` · `RESULTS_SUSPECT` · `COMPLETE`

## Required deliverables for every ECM

Evidence record · applicability decision · baseline parameters · proposed parameters · Sketchbox mapping · interaction notes · result record · confidence · human review disposition · report-ready narrative (plus disclaimer when anonymized/uncalibrated).

## Definition of done

1. Inputs and assumptions serialized  
2. Selected skill checklist passes  
3. Artifacts exist for last confirmed UI/model state  
4. Results pass reasonableness / literature screening where applicable  
5. Limitations reported  
6. Tests pass for changed code  

---

## Repo map

| Path | Role |
|---|---|
| `sketchbox_driver.py` | Auth / probe / browser lifecycle |
| `sketchbox_ui.py` | Shared selectors + `write_and_read_back` |
| `explore_sketchbox.py` | Read-mostly exploration (`mutate=False` by default) |
| `action_sketchbox.py` | Targeted mutations (e.g. cooling offset) |
| `run_measure.py` | Measure add + RESULTS wait (still hardening toward MeasureBrief) |
| `testdrive.py` | Multi-building approved-ECM screen |
| `run_madison_concept.py` | Madison Liberty playbook (schedule then GL36 proxy) |
| `config.py` | Non-secret runtime config from env |
| `schemas/` | building_profile / measure_brief / result_record |
| `examples/buildings/` | Building profiles including Madison Liberty |
| `examples/evidence/` | Synthetic FDD-style evidence packs |
| `.agents/skills/` | Domain + operator skills |
| `.agents/workflows/` | End-to-end + UI recovery |
| `.agents/checklists/` | Readiness / write / QA gates |
| `.cursor/skills/vibe20-sketchbox/` | Cursor discovery skill → this handbook |

Credentials: `SKETCHBOX_EMAIL` / `SKETCHBOX_PASSWORD` in gitignored `.env` only.

### Driver state machine (intent)

`DISCOVER → AUTHENTICATE → LOAD_OR_CREATE → BASELINE_INPUT → BASELINE_VERIFY → BASELINE_RUN → MEASURE_INPUT → MEASURE_VERIFY → MEASURE_RUN → EXPORT → QA → COMPLETE`

Preserve script boundaries; future `app20/` domain/adapters/services layout is optional hardening (typed models, artifact store, MeasureBrief-driven `run_measure.py`).

---

## Sketchbox live facts (operators)

- Tabs: `div.view-link[view="project|design|schedules|measures|results"]` (lowercase).
- Save to account: `.save-project-icon` / `title="Save this project"` (also `open-project-icon` to reopen).
- Project Name: ASCII hyphens only — Unicode em dash `—` is rejected and can disable climate selects.
- Cooling thermostat offset max **5°F**.
- Offset inputs: title contains `cooling setpoint by this offset` / `heating setpoint by this offset`.
- Shells: one per materially different HVAC / schedule / program / geometry — not per floor/room.
- Blue values = responsive defaults; black = constant defaults — never silently override.
- Madison weather: State `Wisconsin`, City `Madison` works; record `sketchbox_baseline_code` separately from `conceptual_existing_building_vintage` (often `unknown`).
- HVAC path used for Liberty concept: **VAV with HW Reheat** + **Direct Expansion** + heating fuel **Natural Gas** — **not** air-cooled chiller (flag `hvac_approx_vav_hw_reheat_dx_not_air_cooled_chiller`).
- Schedule contrast: Simplified + Occupancy `Normal` vs `Always Occupied` (exact 07:00–17:00 matrix not fully automated).
- Add Measure catalog (subset): includes **VAV Box Minimum**, **Fan Power**, setpoints, Empty Measure — **no** named “duct static reset” or “Guideline 36”.

Helpers: `sketchbox_ui.py` (`SELECTOR_MAP_VERSION`).

---

## FDD → ECM workflow (Vibe 19 bridge)

```text
vibe19 analytics package
  → evidence normalization (SCHED-247, AHU-DUCTHI, FC1, VAV minima, …)
  → applicability gates
  → MeasureBrief (approved only)
  → Sketchbox baseline
  → progressive ECMs (one at a time)
  → RESULT records + validation + limitations
```

| vibe19 / evidence | ECM | Sketchbox target |
|---|---|---|
| `SCHED-247` continuous runtime | Schedule align (`schedule-optimization`) | Occupancy Always Occupied → Normal (per shell) |
| High terminal mins / G36 candidate | `gl36-airside` | VAV Box Minimum + Fan Power proxies on both AHUs |
| `AHU-DUCTHI` / `FC1` | Supports DSP-reset **portion** of GL36 proxy | Fan Power (proxy) — not a true DSP control |
| Comfort / SAT faults | `sat-reset` / `vav-minimum-reset` | Only with sensor health gates |

Interaction: run **schedule before GL36**; never sum overlapping fan runtime as independent.

---

## Madison Liberty playbook

Profile: `examples/buildings/madison_liberty_concept.json`  
Evidence: `examples/evidence/madison_liberty_concept_evidence.json`  
Runner: `python run_madison_concept.py`

```text
Baseline: shell Office = Normal; Office (2) = Always Occupied
ECM-1: Office (2) → Normal          (SCHED-247 class)
ECM-2: GL36 proxy both shells       (VAV Box Minimum + Fan Power)
Validate incremental % vs literature bands
```

| ECM | ID | Status intent |
|---|---|---|
| Schedule AHU-2 | `ECM-AHU2-SCHED-ALIGN` | Automate on SCHEDULES tab |
| GL36 airside both AHUs | `ECM-GL36-AIRSIDE-BOTH-AHUS` | Conceptual proxy via MEASURES; flag `gl36_proxy_not_full_sequences` |

ECM-1 mutates shell schedule baseline (not necessarily a MEASURES row). Report `baseline` vs `after_ecm_ahu2_schedule` vs `after_ecm2_gl36`.

```powershell
cd vibe_code_apps_20
python run_madison_concept.py --dry-run
python run_madison_concept.py
```

### Live screening notes (latest)

From `run_madison_concept.py` (conceptual, uncalibrated — Madison weather only):

| Case | $/yr | site EUI | kWh/yr |
|---|---:|---:|---:|
| Baseline (AHU-2 Always Occupied) | ~141,800 | ~42.5 | ~1,255,600 |
| After ECM-1 schedule | ~97,500 | ~31.6 | ~842,900 (~33% kWh) |
| After ECM-2 GL36 proxy | same as ECM-1 when Custom/Better not locked | — | incremental often **0%** until measure cards set away from No Change |

- `sketchbox_baseline_code`: IECC 2018 · HVAC approx: VAV+HW+DX  
- Save: click `.save-project-icon` (**Save this project**) — title should show `Madison Liberty-Style Office` in Open saved projects  
- Validation: schedule ECM in literature-adjacent band for whole-building; GL36 incremental `WARN`/`gl36_incremental_zero_impact` if cards remain **No Change**  
- Flags: `conceptual_gl36_proxy`, `gl36_proxy_not_full_sequences`

---

## GL36 validation bands (domain knowledge)

Published multi-zone VAV G36 studies often show **~20–40% HVAC energy** savings (average near **~31%**). Rough site-energy component magnitudes seen in decompositions: VAV-min **~16%**, SAT reset **~7%**, duct-static reset **~4%**.

Sketchbox reports **whole-building** metrics after a large schedule ECM — expect incremental GL36-proxy kWh savings often in **~5–35%**. Outside that band → `WARN` (not automatic failure). Never equate whole-building % to HVAC-only literature %.

Skill: `.agents/skills/gl36-airside/SKILL.md`.

---

## Integrity / critique backlog

Prior engineering review (governance strong; drivers catching up):

**Patched**

- approved-only measure gate  
- zero offsets → true baseline → measure scrape sequencing  
- `run_id` / `input_hash` / `quality_flags` on result records  
- shared `sketchbox_ui.py` + read-back helper  
- `--dry-run` / `--artifact-dir` on testdrive  
- explore read-only by default  
- Madison schedule ECM + GL36 proxy path  

**Still open**

- MeasureBrief-driven `run_measure.py`  
- jsonschema validation on emit  
- HTML fixture selector tests  
- redaction layer before persisting DOM dumps  
- `--project-id` targeting on all mutating drivers  

Roadmap themes (not a source diary): typed domain models · vibe19 ingest · progressive ECM portfolio · results QA / economics · CI browser contract tests.

---

## Design principles

1. Evidence before modeling.  
2. Measure briefs are authoritative.  
3. One change at a time.  
4. Never hide assumptions.  
5. Baseline integrity first.  
6. Human review gates irreversible actions.  
7. Capture state after major UI transitions under `.artifacts/` (gitignored).
