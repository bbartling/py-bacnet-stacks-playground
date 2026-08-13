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
| [`eplus_gym/envs/lakeside_w2a.py`](../eplus_gym/envs/lakeside_w2a.py) | Lakeside W2A A04 — six `DSM_HTG_SP_*` (or legacy `SCH_HtgSP`) |
| [`eplus_gym_app/`](../eplus_gym_app/) | Pure helpers (site bundle, staging, KPIs). **Streamlit REMOVED** |
| [`scripts/vibe22.py`](../scripts/vibe22.py) | **CLI** status / optimize-day / show / approve / export |
| [`scripts/vibe22_rl.py`](../scripts/vibe22_rl.py) | **CLI** LIVE SB3 PPO/DQN daily RL (`train` / `bakeoff` / `compare`) |
| [`eplus_gym/rl/`](../eplus_gym/rl/) | Day-MDP env, spaces, reward, SB3 train, matplotlib plots |
| [`eplus_gym_app/open_meteo_epw.py`](../eplus_gym_app/open_meteo_epw.py) | Open-Meteo archive → AMY EPW (agent weather tool) |
| [`eplus_gym/train_rllib.py`](../eplus_gym/train_rllib.py) | Pointer stub → SB3 CLI (RLlib not shipped) |
| [`CONTRIBUTING_RL.md`](CONTRIBUTING_RL.md) | rllib-energyplus hygiene + subprocess isolation |

## Run

```powershell
# Day or month lookup (CLI)
python -u scripts\run_eplus_gym_rules.py --mode lookup
python -u scripts\run_eplus_gym_rules.py --mode lookup --month 2026-01

# Grow IdealLoads farm for full months (dry-run first; --execute needs EnergyPlus)
python -u scripts\run_eplus_gym_month_farm.py --months 2026-01,2026-02 --dry-run

# CLI six-zone DSM screening (Streamlit REMOVED)
python -u scripts\vibe22.py status --site-root $env:SITE_ROOT
python -u scripts\vibe22.py optimize-day --day 2026-01-26 --lookback-days 3 --budget 8 --no-cache
# Live DSM campaign (preflight → sequential run_eplus_gym_rules children)
# python -u scripts\run_dsm_campaign.py --site %SITE_ROOT% --request path\to\campaign_request.json
python -u scripts\run_eplus_gym_rules.py --family w2a --mode auto

# Live month closed-loop (CLI only; slow)
# python -u scripts\run_eplus_gym_month_live.py --month 2026-01 --strategy baseline --max-steps 96

# Refresh AMY EPW from Open-Meteo (site lat/lon)
python -u scripts\eplus_fetch_open_meteo_epw.py
```

Notebook viewer: `notebooks\lakeside_eplus_gym_playground.ipynb`  
Artifacts: `reports/eplus_gym/`.

## Weather (AMY vs TMY)

| Kind | Source | Agent tool |
| --- | --- | --- |
| `AMY_OPEN_METEO` | Open-Meteo archive at `answers.json` lat/lon | `scripts/eplus_fetch_open_meteo_epw.py` |
| `TMY_MSN` | Madison Dane County TMY3/TMYx | Manual EnergyPlus weather download |
| `TMY_SCREENING` | Chicago O'Hare / `*screening*` | **Never auto-select** |

AMY is **actual-year M&V**, not typical. Do not invent an EPW from BAS OAT-only.
Multi-year AMY `DATA PERIODS` must use `mm/dd/yyyy` (not `8/1,8/7` noyear) or
EnergyPlus rejects winter RunPeriods. Staged IDFs with Begin/End Year set
Treat Weather as Actual=Yes so E+ uses absolute dates (not Julian mm/dd).
Preflight calls `repair_epw_data_periods`.
Console **Calendar month** defaults to the BAS peak-day month.
Scorecard: **kW trim** (baseline peak − strategy peak) and **kWh penalty**
(strategy kWh − baseline kWh) over the **entire selected window**.
No live `ml/` package — helpers live in `archive/ml/`.
Skill: [`../skills/open-meteo-epw/SKILL.md`](../skills/open-meteo-epw/SKILL.md).

## Site Config (staged setpoints)

`reports/eplus_gym/site_dsm_config.json` (occ/unocc heat/cool °F + occupancy +
optional peak-day override). Staging in `stage_idf_for_period` patches schedules
on the **run copy** only — never overwrite published champions. Six-zone path
adds `DSM_HTG_SP_*` DualSPs via `eplus_native/six_zone_htg_stage.py`.

## EnergyPlus-MCP (agent inspect)

Cursor MCP `user-energyplus` is for inspect / RunPeriod / validate
(`inspect_schedules`, `modify_run_period` on copies, `validate_idf`,
`list_zones`). It is **not** a live setpoint actuator path. See
[`../eplus_gym_app/eplus_mcp_bridge.py`](../eplus_gym_app/eplus_mcp_bridge.py).

## Twin foundation (still live)

- IDF pins: `models/eplus/`
- Staging: `eplus_native/`
- Skills: eplus-gl14, utility-gl14, w2a-plant-dial, open-meteo-epw
- Specs: [`UTILITY_GL14.md`](UTILITY_GL14.md), [`W2A_PLANT_DIAL.md`](W2A_PLANT_DIAL.md)

## Archived product paths

Hybrid ONNX desktop / greybox / control-twin lab: **PURGED** from the tree
(see [`../archive/README.md`](../archive/README.md)). Historical stub:
[`HEATING_DSM.md`](HEATING_DSM.md). Parked helpers remain in [`../archive/ml/`](../archive/ml/).
Streamlit UI: [`../archive/streamlit_ui_2026-08-13/`](../archive/streamlit_ui_2026-08-13/).

## Non-goals (this cut)

- No BACnet writes
- No full PPO campaign
- No claiming IdealLoads treatment = plant savings
- No Streamlit product surface
