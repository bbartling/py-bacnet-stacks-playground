# Heating DSM ML (`ml/`) — vibe22 Hybrid Real+E+

**15-min × 96** hybrid simulator: real BAS baseline + paired EnergyPlus deltas.
Peak window HE **05–09** local (steps 20–36). Honesty: **`HYBRID_SCREENING`**.

## Honesty

| Stamp | Meaning |
| --- | --- |
| `HYBRID_SCREENING` | Ship mode — not tariff-grade until field DSM trials |
| `REAL_BAS_15MIN` | Component A rows (measured only) |
| `ENERGYPLUS_NATIVE_RUN` | Component B paired farm (IdealLoads+COP) |
| `ENERGYPLUS_NATIVE_DELTA` | DSM − baseline targets |
| Ideal Loads + fixed-COP | Twin electric demand (COP 3.5/4.5) — not GSHP/GLHE |

**Do not** concat real BAS and E+ rows. Old kW-only stems notes:
`ml/artifacts/_quarantine_20260806/README.md`.

## Pipeline (CLI SoT)

```powershell
$env:LAKESIDE_SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
$env:VIBE22_ALLOW_CLI_TRAIN="1"
python -u scripts\build_real_15min_store.py
python -u scripts\eplus_heating_dsm_farm.py --smoke   # or --crossed / --medium
python -u scripts\train_four_arms.py --profile full_evaluation
$env:VIBE22_ALLOW_SMOKE_PROMOTE="1"
python -u scripts\ship_best_to_desktop.py
```

Notebooks are **viewers** only. Models/parquets are **not** committed — see [`artifacts/README.md`](artifacts/README.md).

## Artifacts (local / Drive)

| Stem | Role |
| --- | --- |
| `real_baseline_15min_v1.*` | 7-out real baseline (sklearn ship) |
| `eplus_delta_15min_v1.*` | 7-out E+ delta |
| `heating_dsm_eplus_paired_15min_v1.parquet` | Paired farm |
| `hybrid_dsm_96_v1_walk.json` | Desktop ship walk |
| `contracts/hybrid_dsm_96_v1.json` | Versioned I/O (in git) |
| `contracts/hybrid_dsm_96_v2.json` | **Contract-only** sibling — farm **unimplemented**; do not train/promote |

Torch ResMLP → `*_torch_v1.*` under `artifacts/runs/torch_*` (research only).

### Schedule / plant integrity (2026-08-08)

Integrity-first W2A closure (`w2a_integrity_closure_*`): 8 unique post-ExpandObjects live-knob trials; raw gates **FAIL**; DSM **NO-GO**. Prior unreproducible W2A “20/20” / W15–W19 **retracted**. P1 structure gate is **improvement-to-observed** (historical weekend overshoot FAIL). See [`../docs/superpowers/specs/2026-08-08-schedule-plant-campaign-audit.md`](../docs/superpowers/specs/2026-08-08-schedule-plant-campaign-audit.md).

Agent SoT: [`../vibe22_agent_spec/HEATING_DSM.md`](../vibe22_agent_spec/HEATING_DSM.md).
