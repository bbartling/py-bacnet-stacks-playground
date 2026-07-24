---
name: wattlab-twin-calibrate-dial
description: >-
  Dial EnergyPlus Twin models vs utility bills (G14). Use when gas/elec is short
  or long vs monthly bills, Twin calibrate, WWR/glass/infil ladders, seasonal SAT
  / VAV reheat / DAT dump, or stacked Floor_1–N twins. Triggers on: calibrate,
  G14, CVRMSE, short gas, short elec, dial knobs, WWR, infiltration, discharge
  air temp, reheat, AMY bills, calibration_scorecard.
---

# WattLab Twin calibrate dial playbook

EnergyPlus **autosizes** plant/coils when fields are `autosize`. You dial
**envelope + loads + as-operated HVAC setpoints** — not nameplate tons — unless
the human supplies them.

Canonical doc: [`../../docs/TWIN_DIAL_PLAYBOOK.md`](../../docs/TWIN_DIAL_PLAYBOOK.md).
Tools bin: [`../../docs/AGENT_TOOLS.md`](../../docs/AGENT_TOOLS.md).
Assumptions hierarchy: [`../wattlab-assumptions/SKILL.md`](../wattlab-assumptions/SKILL.md).

## Phase 0 — Geometry lock (do this first)

1. Confirm the twin the human expects (e.g. **stacked floors × 1 zone** =
   `Floor_1`…`Floor_N`).
2. **Refuse** DOE mid×4 (`Basement` / `Core_mid` / `Perimeter_*`) as the campus
   twin when the user wants stacked floors.
3. Weather for G14: **AMY** overlapping bill months (not TMY screening).
4. Bills: correct CSV (shared elec once + **that building’s** gas).
5. One hypothesis per `runs/<id>/`; publish + `calibration_scorecard.json`.

## Phase 1 — Annual fuel short/long (envelope + internal gains)

### Gas / heating **short** (model ≪ bills annually)

Ordered knobs (stop when annual gas enters ~±5% or overshoots):

1. Raise **WWR** toward site reality (curtain wall often **0.70–0.75**).
2. Leaky glass: assembly **U ≈ 0.80–1.0 IP** (~4.5–5.7 SI), not pretty DOE glass.
3. Raise **infiltration** (ACH ladder).
4. Only then HVAC shape knobs (Phase 2).

### Electric **short** (model ≪ bills)

- Raise **LPD / EPD** (W/m²). Prefer this over random chiller oversizing.
- Hold LPD/EPD while chasing gas shape once annual elec is near gate.

### Gas **long** / elec **long**

- Reverse the same knobs (tighter glass, less ACH, lower LPD/EPD).

## Phase 2 — Monthly **shape** (annual flat but CVRMSE fails)

Classic failure: **winter/shoulder gas high, summer gas low** (annual cancels).

### Read vibe19 AHU DAT before inventing SAT

- Map `discharge-air-temp` / `discharge-air-temp-sp` by month (fan-on).
- Cold dump + aggressive VAV reheat is often as-operated — match it with
  **banded** SAT, do not invent year-round constant dumps.

### Shape knobs (keep envelope locked once annual is close)

| Symptom | Knob |
| --- | --- |
| Summer gas low | Cooler summer **DAT/SAT**, raise **VAV min-flow** in true summer |
| Winter gas high | Warmer winter SAT, **shorter winter OA** hours, lower winter min-flow |
| Shoulder spikes from long cold-dump window | **Band** SAT (cold dump peak summer only; warmer shoulders) |
| Bills ≠ HDD | Do not force physics-only; band months; note residual CV floor |

Prefer **seasonal / banded** `Schedule:Compact` on cooling SAT + scheduled VAV
min-flow fraction over year-round constant min-flow bumps.

### Honesty

- G14 pass = both fuels \|NMBE\|≤5% **and** CVRMSE≤15%.
- Annual % alone is **not** calibrated.
- Document residual: bill shape may not track HDD (log it).

## Phase 3 — Publish / freeze

```text
sim → score_g14_monthly (or wattlab score-monthly)
  → write_calibration_scorecard → publish_run_for_studio
  → optional save_best_model.py --set-current
```

Stamp WWR / U / ACH / SAT bands / min-flow / OA on `dial_meta.json` /
`run_manifest.json`. Twin charts need nested `calibration_scorecard.json`
(`utility_bills.stats_*`) — not a bare `g14_score.json` alone.

## Workspace pointers

- Playbook: `vibe20_agent_spec/docs/TWIN_DIAL_PLAYBOOK.md` (and optional
  `/data/tools/TWIN_DIAL_PLAYBOOK.md`)
- Session log: `/data/reports/CALIBRATE_SESSION.md`
- Score / scorecard / ladders: `/data/tools/` — see `AGENT_TOOLS.md`
- Studio: chronological run #, dial knobs table, ECMs best-G14 baseline
