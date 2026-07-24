---
name: wattlab-assumptions
description: >-
  Use when building sparse / minimal-info EnergyPlus twins: defaults hierarchy,
  Ideal Loads vs explicit HVAC, PNNL infiltration/OA candidates, assumption
  ledger, TMY→AMY ladder, and short/long fuel G14 dial (WWR/glass/ACH then
  banded SAT/reheat). Triggers on: sparse building, minimal info, defaults,
  IdealLoads, assumption ledger, autosize, constrain plant, TMY, AMY, prototype,
  short gas, CVRMSE, calibrate dial, WWR, infiltration.
---

# WattLab assumptions — agent is the assumption-maker

EnergyPlus simulates; **you** choose, justify, and log defaults. EnergyPlus-MCP
inspects/patches/sims — it does not pick TMY vs AMY or invent city/area.

Full ladder: [`../../docs/SPARSE_BUILDING_PLAYBOOK.md`](../../docs/SPARSE_BUILDING_PLAYBOOK.md).
Fuel dial depth: [`../wattlab-twin-calibrate-dial/SKILL.md`](../wattlab-twin-calibrate-dial/SKILL.md)
· [`../../docs/TWIN_DIAL_PLAYBOOK.md`](../../docs/TWIN_DIAL_PLAYBOOK.md).

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

## Short / long fuel playbook (Twin G14 dial)

Autosized plant is fine for sparse twins — dial **envelope + loads + as-operated
SAT/VAV**, not invented nameplate tons. Full playbook:
[`../../docs/TWIN_DIAL_PLAYBOOK.md`](../../docs/TWIN_DIAL_PLAYBOOK.md) (Cursor skill:
`wattlab-twin-calibrate-dial`). Tools publish chain: [`../../docs/AGENT_TOOLS.md`](../../docs/AGENT_TOOLS.md).

### Gas short annually (model ≪ bills)

1. Lock **good geometry** (e.g. stacked `Floor_1`…`Floor_N` — not DOE mid×4 when
   the human wants floor massing).
2. Raise **WWR** toward site (curtain wall often 0.70–0.75).
3. Leaky glass: **U ≈ 0.80–1.0 IP**, not pretty DOE U.
4. **Infiltration ACH** ladder; stop near annual gas ±5%.
5. Only then HVAC shape (below).

### Elec short annually

- Raise **LPD / EPD** (W/m²) before plant oversizing.

### Annual flat but monthly gas CVRMSE fails (winter high / summer low)

1. Read vibe19 **AHU discharge-air-temp / SP** by month (fan-on).
2. Summer dump (often ~**50°F** when dump shows it) + higher **VAV min-flow** in
   true summer only.
3. Warmer winter SAT + shorter winter OA; **band** months — do **not** hold cold
   dump across long shoulder seasons (blows Oct/Aug gas).
4. If bills ≠ HDD (Feb peak / Oct tiny), band aggressively and document residual CV.

G14 pass = both fuels \|NMBE\|≤5% **and** CVRMSE≤15%. Annual % alone ≠ calibrated.
Always write `calibration_scorecard.json` in the Twin-expected nested shape.

## Do not

- Invent office / Madison / Chicago for a real dump.
- Claim G14 on TMY vs non-overlapping bills or unscaled ~10k ft² prototype.
- Quietly publish ROI when guardrails hit `INVESTIGATE`.
- Call stacked-twin calibrate “done” on DOE mid×4 zoning when the user expects Floor_1–N.
- Start gas-short campaigns with plant oversizing before envelope / infil.
