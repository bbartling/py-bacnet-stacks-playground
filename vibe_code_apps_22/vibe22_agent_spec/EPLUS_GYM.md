# Vibe 22 — EnergyPlus control gym (Lakeside)

**Last validated:** 2026-08-11 · Human DSM = W2A A04; IdealLoads is CLI structural only.

**Inspiration:** [airboxlab/rllib-energyplus](https://github.com/airboxlab/rllib-energyplus)
(Gym + `pyenergyplus` queue/callback runner). We borrow the **runner shape**, not Ray/PPO
as the shipped product.

## Product question

> For a chosen outdoor day, what is the **15-min × 96** facility kW and heating
> setpoint trajectory on the **published W2A A04 champion** under named rule DR
> strategies (`baseline`, `flat_24_7`, `deep_setback`, …), with lookup if an A04
> farm exists else live E+ step control?

## Release posture

| Mode | Provenance | When |
|---|---|---|
| `lookup` | `FARM_LOOKUP_EMULATOR` | Site paired farm parquet — offline turnkey |
| `live` | `ENERGYPLUS_PYTHON_API` | EnergyPlus + `ENERGYPLUS_ROOT` + EPW/IDF |
| `auto` | either | Live if API + paths, else lookup |

**Honesty:** W2A A04 = **`W2A_PHYSICAL_DSM`**. IdealLoads = **`STRUCTURAL_LOAD_DIAGNOSTIC`**.  
`promote=False`. W2A auto never falls back to IdealLoads farm. ≠ field BAS meter.

## Package

| Module | Role |
|---|---|
| [`eplus_gym/runner.py`](../eplus_gym/runner.py) | Threaded E+ + obs/act queues (rllib-energyplus shape) |
| [`eplus_gym/env.py`](../eplus_gym/env.py) | Abstract Gymnasium `EnergyPlusEnv` |
| [`eplus_gym/envs/lakeside_idealloads.py`](../eplus_gym/envs/lakeside_idealloads.py) | Lakeside IdealLoads — actuate `SCH_HtgSP` |
| [`eplus_gym/controllers.py`](../eplus_gym/controllers.py) | Rule policies from `contracts/control_strategies_v1` |
| [`eplus_gym/lookup_emulator.py`](../eplus_gym/lookup_emulator.py) | Farm parquet stand-in |
| [`eplus_gym/month_calendar.py`](../eplus_gym/month_calendar.py) | Calendar-month farm/coverage helpers |
| [`eplus_gym/simulate.py`](../eplus_gym/simulate.py) | `run_rule_episode` / `run_rule_month_lookup` |
| [`eplus_gym/envs/lakeside_w2a.py`](../eplus_gym/envs/lakeside_w2a.py) | Lakeside W2A A04 — actuate `SCH_HtgSP` |
| [`eplus_gym_app/`](../eplus_gym_app/) | **Streamlit DSM console** (published pack; live E+ via CLI subprocess) |
| [`eplus_gym/train_rllib.py`](../eplus_gym/train_rllib.py) | RLlib stub (not shipped) |

## Run

```powershell
# Day or month lookup (CLI)
python -u scripts\run_eplus_gym_rules.py --mode lookup
python -u scripts\run_eplus_gym_rules.py --mode lookup --month 2026-01

# Grow IdealLoads farm for full months (dry-run first; --execute needs EnergyPlus)
python -u scripts\run_eplus_gym_month_farm.py --months 2026-01,2026-02 --dry-run

# Streamlit DSM console (lookup in-process; live via CLI subprocess)
streamlit run eplus_gym_app\streamlit_app.py --server.port 8765
python -u scripts\run_eplus_gym_rules.py --family w2a --mode auto

# Live month closed-loop (CLI only; slow)
# python -u scripts\run_eplus_gym_month_live.py --month 2026-01 --strategy baseline --max-steps 96
```

Notebook viewer: `notebooks\lakeside_eplus_gym_playground.ipynb`  
Artifacts: `reports/eplus_gym/`.

## Twin foundation (still live)

- IDF pins: `models/eplus/`
- Staging: `eplus_native/`
- Skills: eplus-gl14, utility-gl14, w2a-plant-dial
- Specs: [`UTILITY_GL14.md`](UTILITY_GL14.md), [`W2A_PLANT_DIAL.md`](W2A_PLANT_DIAL.md)

## Archived product paths

Hybrid ONNX desktop, grey-box 1R1C, control-twin lab, phys-LSTM notebooks:

→ [`../archive/2026-08-10_pre_eplus_gym/README.md`](../archive/2026-08-10_pre_eplus_gym/README.md)

Historical hybrid spec stub: [`HEATING_DSM.md`](HEATING_DSM.md).

## Non-goals (this cut)

- No BACnet writes
- No full PPO campaign
- No claiming IdealLoads treatment = plant savings
