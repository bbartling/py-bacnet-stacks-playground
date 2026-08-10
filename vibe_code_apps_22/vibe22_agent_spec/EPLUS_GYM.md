# Vibe 22 — EnergyPlus control gym (Lakeside)

**Last validated:** 2026-08-10 · Product SoT after archive cut.

**Inspiration:** [airboxlab/rllib-energyplus](https://github.com/airboxlab/rllib-energyplus)
(Gym + `pyenergyplus` queue/callback runner). We borrow the **runner shape**, not Ray/PPO
as the shipped product.

## Product question

> For a chosen outdoor day, what is the **15-min × 96** IdealLoads electric proxy
> and heating setpoint trajectory under **named rule DR strategies**
> (`baseline`, `flat_24_7`, `deep_setback`, …), with a path to **live E+ step control**
> and optional RL later?

## Release posture

| Mode | Provenance | When |
|---|---|---|
| `lookup` | `FARM_LOOKUP_EMULATOR` | Site paired farm parquet — offline turnkey |
| `live` | `ENERGYPLUS_PYTHON_API` | EnergyPlus + `ENERGYPLUS_ROOT` + EPW/IDF |
| `auto` | either | Live if API + paths, else lookup |

**Honesty:** IdealLoads = **`STRUCTURAL_LOAD_DIAGNOSTIC`**. `promote=False`.  
≠ W2A plant twin; ≠ field BAS meter; ≠ operational DSM.

## Package

| Module | Role |
|---|---|
| [`eplus_gym/runner.py`](../eplus_gym/runner.py) | Threaded E+ + obs/act queues (rllib-energyplus shape) |
| [`eplus_gym/env.py`](../eplus_gym/env.py) | Abstract Gymnasium `EnergyPlusEnv` |
| [`eplus_gym/envs/lakeside_idealloads.py`](../eplus_gym/envs/lakeside_idealloads.py) | Lakeside IdealLoads — actuate `SCH_HtgSP` |
| [`eplus_gym/controllers.py`](../eplus_gym/controllers.py) | Rule policies from `contracts/control_strategies_v1` |
| [`eplus_gym/lookup_emulator.py`](../eplus_gym/lookup_emulator.py) | Farm parquet stand-in |
| [`eplus_gym/simulate.py`](../eplus_gym/simulate.py) | `run_rule_episode` |
| [`eplus_gym/train_rllib.py`](../eplus_gym/train_rllib.py) | RLlib stub (not shipped) |

## Run

```powershell
python -u scripts\run_eplus_gym_rules.py --mode lookup
# notebook
notebooks\lakeside_eplus_gym_playground.ipynb
```

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
