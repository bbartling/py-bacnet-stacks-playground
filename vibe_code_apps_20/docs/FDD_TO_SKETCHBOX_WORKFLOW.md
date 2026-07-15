# FDD → Sketchbox ECM screening workflow

**Scope:** How vibe_code_apps_19 Open-FDD / RCx analytics should feed vibe_code_apps_20
conceptual Sketchbox screening. This is the intended product bridge — not yet a live
API between the two apps.

## Disclaimer (required on every conceptual export)

> This is a conceptual, uncalibrated screening model for an anonymized office building.
> It is not a design load calculation, code-compliance model, calibrated energy model,
> or representation of a specific Madison property.

## End-to-end sketch

```text
vibe19 analytics package
  → evidence normalization (SCHED-247, AHU-DUCTHI, FC1, …)
  → applicability gates
  → MeasureBrief (approved)
  → Sketchbox baseline (weather + shells + VAV defaults)
  → progressive ECMs (one at a time)
  → RESULT records + confidence + limitations
```

## Example FDD → ECM maps (Madison Liberty concept)

| vibe19 signal | ECM | Sketchbox target | Notes |
| --- | --- | --- | --- |
| `SCHED-247` on AHU-2 (24/7 fan) | `ECM-AHU2-SCHED-ALIGN` | Shell-2 schedule → occupied hours | Prefer **two shells** when AHUs differ in schedule |
| `AHU-DUCTHI` / `FC1` on AHU-1/2 | `ECM-AHU-DUCT-STATIC-RESET` | MEASURES fan/static reset if present | Do **not** invent savings if UI has no mapping |
| Motor runtime / fan-on hours | schedule_optimization skill | Occupied vs observed runtime | Quantify avoidable hours before modeling |

Interaction rule: run schedule alignment **before** static-pressure reset savings claims,
and never sum overlapping fan-energy reductions as independent.

**Note on Madison ECM-1 automation:** Occupancy Always Occupied → Normal is applied on the
**SCHEDULES** tab for shell Office (2). That mutates the shell baseline, not a MEASURES-row
progressive measure. Report the pair as `baseline` vs `after_ecm_ahu2_schedule`. Prefer a true
Sketchbox Measure later when a catalog control exists.

## Shell rule (from Sketchbox knowledge)

One shell per materially different HVAC / schedule / program / geometry.

Madison Liberty concept:

- SHELL-AHU-1 — 75,000 ft² — occupied Mon–Fri 07:00–17:00, Sat 07:00–14:00
- SHELL-AHU-2 — 75,000 ft² — baseline 24/7; ECM puts it on AHU-1 schedule

Geometry/glazing identical unless evidence says otherwise.

## Scripts

```powershell
cd vibe_code_apps_20
python run_madison_concept.py --dry-run
python run_madison_concept.py --probe-only   # inventory DESIGN/SCHEDULES/MEASURES
python run_madison_concept.py                # configure Madison + baseline scrape + map gaps
python testdrive.py --buildings examples/buildings --dry-run
```

Profiles:

- `examples/buildings/madison_liberty_concept.json`
- `examples/evidence/madison_liberty_concept_evidence.json` (synthetic until real vibe19 export)

## Sketchbox realities from Madison Liberty live test (2026-07)

| Requested | Closest UI support | Status |
| --- | --- | --- |
| Madison, WI weather | State=Wisconsin, City=Madison | Works |
| IECC baseline | IECC 2018 (account selectable) | Record separately from building vintage |
| 2 shells @ 75k ft² | Add Shell → Office / Office (2) | Works |
| Central VAV + air-cooled chiller | **VAV with HW Reheat** + **DX** (no ACC option on this path) | Approximated + flagged |
| AHU-1 07:00–17:00 / Sat half-day | Simplified + Occupancy **Normal** (~9–5 weekday preset) | Approximated |
| AHU-2 24/7 | Occupancy **Always Occupied** | Works for baseline contrast |
| ECM put AHU-2 on schedule | Office (2) Always Occupied → Normal | Automates |
| Duct static reset both AHUs | Not in Add Measure catalog | **NEEDS_INPUT** — do not invent |

Heating fuel used for HW reheat path: **Natural Gas** (flagged assumption).

```powershell
python run_madison_concept.py --dry-run
python run_madison_concept.py
```
