# Lakeside Control Twin Lab V1

**Status:** PR1 design SoT — dual-track after grey-box verdict  
`INSUFFICIENT_HVAC_INPUT_SENSOR_HUNT_REQUIRED`  
**Honesty:** lab plant-electric = `SYNTHETIC_W2A_PROVENANCE` / `NON_PROMOTABLE`  
**Hybrid:** remains `HYBRID_SCREENING` / IdealLoads = `STRUCTURAL_LOAD_DIAGNOSTIC`  
**BACnet:** read-only future surface only — **no WriteProperty**

## Why this lab exists

Grey-box 1R1C on measured data is bound-stuck (persistence-like) without plant
actuators. Escalating RC order will not invent Q. This lab follows BOPTEST /
Radecki posture:

- **High-fidelity emulator** = W2A A04 champion as **read-only seed** (never overwrite)
- **Measured BAS** remains the deployed-state anchor for any future advisor
- **Plant electric map** learned first from W2A synthetic trajectories

## Honesty layers

| Layer | Source of truth | May claim |
|---|---|---|
| Thermal state (future) | Measured midnight zones + weather | Comfort only after grey-box ID gate A |
| Plant electric map | W2A A04 staged lab runs | `SYNTHETIC_W2A_PROVENANCE` — never field compressor kW |
| Site BAU / non-HVAC | Real `facility_kw` sklearn baseline | Screening hybrid IdealLoads Δ |

Optimizer shape (future, not this PR):

```text
P_site ≈ P_non_hvac(sklearn) + P_hvac(W2A_surrogate(state, weather, controls))
```

GO requires treatment uncertainty smaller than economic separation among strategies.
Until then: **lab metrics only**.

## Case matrix

| Axis | Values |
|---|---|
| Strategies | `baseline`, `stagger_preheat`, `deep_setback`, `flat_24_7` (+ farm-only `prbs`) |
| Spin-up / pre-roll | 0 / 3 / 7 / 14 days |
| Timestep | 4 / 6 / 12 steps per hour |

Profiles:

- `smoke` — 1 eval day × 2 strategies × spin0 × ts6 (CI / laptop)
- `full_lab` — full matrix (site job; hours; not CI)

## Packages / scripts

- `ml/control_twin_lab/` — seed, cases, runner, extract, surrogate
- `scripts/run_control_twin_lab.py` — CLI entry
- `scripts/mine_plant_point_candidates.py` — Track A archaeology
- `scripts/eplus_w2a_dsm_farm_scaffold.py` — stage A04 copies (shared)

## Artifacts

- `reports/eplus/spinup_sensitivity.csv`
- `reports/eplus/timestep_sensitivity.csv`
- `reports/ml/dsm_treatment_scorecard.csv`
- `reports/ml/w2a_plant_electric_surrogate_card.json`
- `docs/audits/plant_point_candidates.md`

## Explicit non-claims

- W2A surrogate ≠ Lakeside field compressor kW
- IdealLoads+COP farm ≠ this lab
- Lab PRBS ≠ BACnet writes
- Short spin-up ≠ GLHE seasonal continuous ground init
- Filling CSVs ≠ desktop promote

## Track A exit

Either ≥1 of `{hp_enable_or_stage, loop_ewt, fan_status}` becomes
`PRESENT_IN_EXPORT`, or archaeology documents **NOT_IN_HISTORIAN**.
Grey-box stays diagnostic until then — no six-zone clone.

## References

- Bacher & Madsen (2011) — forward-select complexity
- Radecki & Hencey — grey-box + emulator priors
- Blum et al. BOPTEST (2021) — controller vs emulator API
