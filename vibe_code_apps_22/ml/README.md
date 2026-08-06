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

**Do not** concat real BAS and E+ rows. Old kW-only stems:
`ml/artifacts/_quarantine_20260806/`.

## Pipeline

```powershell
$env:LAKESIDE_SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
python -u scripts\build_real_15min_store.py
python -u ml\train_real_baseline_15min.py --winter-only
python -u scripts\eplus_heating_dsm_farm.py --smoke   # or --medium
python -u ml\train_eplus_delta_15min.py
python -u scripts\promote_hybrid_ship.py
cd desktop; cargo run --release
```

## Artifacts

| Stem | Role |
| --- | --- |
| `real_baseline_15min_v1.*` | 7-out real baseline (ExtraTrees ship) |
| `eplus_delta_15min_v1.*` | 7-out E+ delta (RandomForest) |
| `heating_dsm_eplus_paired_15min_v1.parquet` | Paired farm |
| `hybrid_dsm_96_v1_walk.json` | Desktop ship walk |
| `contracts/hybrid_dsm_96_v1.json` | Versioned I/O |

Torch ResMLP: `train_real_baseline_torch_15min.py` / `*_torch_v1.*` — alternate only.

Agent SoT: [`../vibe22_agent_spec/HEATING_DSM.md`](../vibe22_agent_spec/HEATING_DSM.md).
