---
name: wattlab-assumptions
description: >-
  Use when building sparse / minimal-info EnergyPlus twins: defaults hierarchy,
  Ideal Loads vs explicit HVAC, PNNL infiltration/OA candidates, assumption
  ledger, TMY→AMY ladder. Triggers on: sparse building, minimal info, defaults,
  IdealLoads, assumption ledger, autosize, constrain plant, TMY, AMY, prototype.
---

# WattLab assumptions — agent is the assumption-maker

EnergyPlus simulates; **you** choose, justify, and log defaults. EnergyPlus-MCP
inspects/patches/sims — it does not pick TMY vs AMY or invent city/area.

Full ladder: [`../../docs/SPARSE_BUILDING_PLAYBOOK.md`](../../docs/SPARSE_BUILDING_PLAYBOOK.md).

## Hierarchy (strict order)

1. **Human / FM facts** — `building_type`, `city`, `floor_area_ft2`, lat/lon,
   nameplate tons/hp, known schedules. `NEEDS_INPUT` if missing. Never invent.
2. **Evidence** — vibe19 dump (schedules, setpoints, FDD, weather_observed),
   campus bills, `buildings.json`.
3. **Seed model** — nearest archetype IDF (today: `5ZoneAirCooled` screening) or
   human `custom_idf` / future DOE–PNNL prototype by type/size/code/climate.
4. **Code / climate catalog** — WattLab `defaults` (archetypes, climate.json,
   codes). Unknown city keeps user label + honest substitute EPW note (no silent
   Madison remap).
5. **Literature defaults** (stamp source) — ASHRAE-style schedules; OA methods;
   PNNL infiltration candidate when no measured leakage.

## Partition like a good conceptual modeler

| Stage | Focus |
| --- | --- |
| Project | Site, area, climate, bills window, rates |
| Design | Simple shell / prototype; perimeter-core OK for screening |
| Schedules | Occupancy / lighting / equipment / HVAC avail |
| Baseline | LPD, EPD, people density, ventilation, infil, setpoints |
| Measures | One hypothesis per `runs/<id>/` |
| Results | Monthly vs bills, unmet hours, area scale, weather mode, peak kW, G14 |

After TMY screening: `wattlab calibrate-campaign` (bill months → AMY → G14) —
[`../../docs/CALIBRATE_AND_DELIVERABLES.md`](../../docs/CALIBRATE_AND_DELIVERABLES.md).

Hard-size nameplate: scale by `1/prototype_area_scale` when scale > 1.5; refuse
outside [0.25, 4.0]. City `troy` → detroit catalog (user label preserved).

## Ideal Loads vs explicit system

- **Quick model, not all details known** → Ideal Loads + rigorous envelope /
  schedule assumptions first (when IDF path supports it).
- **Compare HVAC pathways / plant ECMs** → explicit seed (5Zone VAV today);
  always show `prototype_area_scale` vs target ft².
- Keep scenarios separate: (A) autosized conceptual, (B) constrained to
  nameplate, (C) outage/recovery. Never merge into one “truth” run.

## Assumption ledger (publish every campaign)

For each key: value, source (`user` / `dump` / `default` / `literature`),
confidence (high/med/low), sensitivity note.

Minimum keys: occupancy density, LPD, EPD, OA rate method, infiltration,
thermostat / fan hours, WWR, HVAC family, weather mode
(`TYPICAL_YEAR_SCREENING` / `ACTUAL_YEAR_CALIBRATION` /
`SUBSTITUTE_CLIMATE_CONCEPTUAL_ONLY`), `prototype_area_scale`.

## Do not

- Invent office / Madison / Chicago for a real dump.
- Claim G14 on TMY vs non-overlapping bills or unscaled ~10k ft² prototype.
- Quietly publish ROI when guardrails hit `INVESTIGATE`.
