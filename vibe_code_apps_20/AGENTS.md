# AGENTS.md — OpenFDD WattLab (agent OS)

**Single entrypoint for agents.** Prefer this file over scattered notes. Domain skills under `.agents/skills/` remain the procedure detail; routing is `.agents/routing.md`.

**Product:** OpenFDD WattLab — AI helper that turns **Open-FDD / Vibe App 19** findings into auditable **EnergyPlus** ECM energy screens (Dockerized via LBNL EnergyPlus-MCP).

**Quick link (vibe19 historian zips):** [`../vibe_code_apps_19/docs/PACKAGE_SPEC.md`](../vibe_code_apps_19/docs/PACKAGE_SPEC.md) — `openfdd_package_v1` layout before bridging / calibrating.

## Mission

`vibe19 analytics → Model Seed Bundle (schedules + signatures + weather) → optional calibrate.py (AMY EPW + scorecard) → approved MeasureBrief → WattLab easy button (prototype IDF + EPW) → progressive IDF ECMs → result_record + literature QA`

Optimize for engineering defensibility, reproducibility, and honest limits (uncalibrated prototypes are screens, not calibrated models).

### Conceptual disclaimer (required on anonymized / uncalibrated exports)

> This is a conceptual, uncalibrated screening model for an anonymized office building. It is not a design load calculation, code-compliance model, calibrated energy model, or representation of a specific Madison property.

## Mandatory reading order

1. This file (`AGENTS.md`)
2. `.agents/routing.md`
3. `.agents/policies.md`
4. `.agents/data_contract.md`
5. The selected skill’s `SKILL.md`
6. The applicable checklist under `.agents/checklists/`

## Hard rules

- Never commit `.env`, passwords, tokens, customer data, or EnergyPlus output dumps with PII.
- Never invent savings. Missing evidence → `NEEDS_INPUT`.
- Never claim EnergyPlus-MCP alone implements full ASHRAE Guideline 36 — WattLab uses **app-owned IDF patches** for schedule / VAV-min / fan proxies (`conceptual_gl36_proxy`).
- Never skip Docker for live sims: image `energyplus-mcp-dev` (EnergyPlus 26.1) is required.
- Never overwrite a prior run’s IDF without hashing (`input_hash` = SHA-256 of IDF); write `run_manifest.json` with model/weather hashes + EP pin.
- Never silently substitute weather — stamp `weather_suitability` (`TYPICAL_YEAR_SCREENING` / `ACTUAL_YEAR_CALIBRATION` / `SUBSTITUTE_CLIMATE_CONCEPTUAL_ONLY`) on every report.
- Never claim `VALIDATED` without a held-out bill period (`--validation-months`) that passes Guideline-14 gates; no bills or substitute weather → `CONCEPTUAL_ONLY`.
- Never bundle interacting ECMs while reporting them as independent savings — apply one approved measure at a time.
- Never publish utility savings or payback without listing rate and confidence assumptions.
- Never expose the actual building location when the project is marked anonymized.
- Do not claim fake “public product API” wrappers beyond documented Docker / MCP / easy-button surfaces.

## Standard statuses

`READY` · `NEEDS_INPUT` · `NEEDS_ENGINEERING_REVIEW` · `MODEL_RUN_FAILED` · `RESULTS_SUSPECT` · `COMPLETE`

## Required deliverables for every ECM

Evidence record · applicability decision · baseline parameters · proposed parameters · `idf_patch` mapping · interaction notes · result record · confidence · human review disposition · report-ready narrative (plus disclaimer when anonymized/uncalibrated).

## Definition of done

1. Inputs and assumptions serialized  
2. Selected skill checklist passes  
3. Artifacts under `.artifacts/wattlab_<run_id>/`  
4. Results pass reasonableness / literature screening where applicable  
5. Limitations reported  
6. Tests pass for changed code  

---

## Repo map

| Path | Role |
|---|---|
| `wattlab_defaults.py` | responsive-defaults defaults resolver (`field_sources` provenance) |
| `defaults/` | Archetypes, climate, code vintages |
| `easy_button.py` | Prototype → calibrate knobs → baseline → ECM chain (`--measure-set`, `--minimal`) |
| `vibe19_bridge.py` | vibe19 agent-export → evidence + suggested measures |
| `madison_office.py` | Madison conceptual playbook wrapper |
| `ep_docker.py` | Docker image ensure + `energyplus` runs |
| `ep_mcp_client.py` | MCP parity helpers / status smoke |
| `idf_patches/` | Schedule, chiller lockout, SAT reset, GL36-proxy IDF patches |
| `ecm_library/measure_sets.json` | Good / Better / Best progressive sets |
| `results_parse.py` | `eplustbl` → annual + monthly + `savings_by_measure` |
| `config.py` | Paths, image name, default EPW/prototype |
| `schemas/` | building_profile / measure_brief / result_record |
| `examples/buildings/` | WattLab building profiles (EP-oriented) |
| `examples/prototypes/` | Bundled IDF samples |
| `examples/weather/` | Bundled EPW samples |
| `third_party/` | EnergyPlus-MCP pin + clone instructions |
| `.agents/skills/` | Domain + operator skills |
| `.cursor/skills/openfdd-wattlab/` | Cursor discovery skill → this handbook |

## Easy button vs full MCP toolkit

| Mode | When | How |
|---|---|---|
| **Easy button** | Demo / default ECM screen | `python easy_button.py --building ...` or `--minimal '{...}' --measure-set best` |
| **Defaults only** | Form preview / UI | `python wattlab_defaults.py --type office --city madison` |
| **vibe19 bridge** | Auto-suggest ECMs from FDD export | `python vibe19_bridge.py <export_dir>` |
| **Full EnergyPlus-MCP** | Inspect loops, plots, custom run periods, validate IDF | Cursor MCP → Docker `energyplus-mcp-dev` (see `third_party/README.md`) |

### Calibration knobs MCP can vs cannot do

- **Can (MCP modify tools):** people / lights / electric equipment / infiltration multipliers — use when vibe19 gives intensity or runtime hints; else leave 1.0 + `NEEDS_INPUT`.
- **Cannot (WattLab IDF patches):** full occupancy schedule redesign for fan/HVAC avail; VAV box minimums; fan pressure / power curve proxies for Guideline 36 airside. **Do not claim MCP alone does G36.**

## Live facts

- Image: `energyplus-mcp-dev` · EnergyPlus **26.1.0**
- Default prototype: `examples/prototypes/5ZoneAirCooled.idf`
- Madison EPW: Chicago O'Hare TMY3 proxy (`examples/weather/...`) until a WI file is bundled — always record `epw_note` + `weather_suitability=SUBSTITUTE_CLIMATE_CONCEPTUAL_ONLY`
- Artifacts: `.artifacts/wattlab_<UTC>/` with IDF copies, `eplustbl.*`, `result_record_*.json`, `wattlab_report.json`, `run_manifest.json`

## Madison playbook

1. Evidence: SCHED-247 always-on + GL36 applicability (see `examples/evidence/madison_office_evidence.json`)
2. Baseline: continuous fan/coil availability patch on 5ZoneAirCooled + Chicago EPW proxy
3. **ECM-AHU-SCHED-ALIGN** → occupied office availability (07:00–17:00 weekdays)
4. **ECM-GL36-AIRSIDE** → VAV min 0.30→0.15 + fan pressure / min-flow proxies
5. Literature: whole-building incremental GL36-proxy kWh often **~5–35%** after a large schedule ECM; HVAC-only studies avg ~31% — do not equate them

```powershell
cd vibe_code_apps_20
python madison_office.py --dry-run
python madison_office.py
```

## Primary workflow

`OpenFDD / Vibe 19 export → evidence → ECM candidates → review → WattLab easy-button baseline → progressive measures → validation → RCx package`
