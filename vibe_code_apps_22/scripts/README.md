# vibe22 scripts map

**Product SoT (2026-08-13):** CLI six-zone screening — [`scripts/vibe22.py`](vibe22.py).  
Agent loop: [`../vibe22_agent_spec/AGENT_LOOP.md`](../vibe22_agent_spec/AGENT_LOOP.md).  
Parked GL14 helpers: [`../archive/ml/`](../archive/ml/). Hybrid lab scripts: **purged**.

## Product

| Script | Role |
| --- | --- |
| `vibe22.py` | **CLI** status / optimize-day / show-study / approve / export |
| `vibe22_rl.py` | **CLI** LIVE SB3 daily RL (`train` / `bakeoff` / `compare` / `pretrain` / `midnight-tick` / `report` / `campaign`) |
| `gate_six_zone_actuation.py` | Real E+ six DualSP perturbation gate |
| `ingest_site_pack.py` | Zip/folder → site layout + `site_ui_bundle_v1.json` |
| `eplus_fetch_open_meteo_epw.py` | Open-Meteo archive @ site lat/lon → AMY EPW |
| `run_eplus_gym_rules.py` | Rule DR (`--family w2a\|idealloads`, `lookup` / `live` / `auto`) |
| `run_eplus_gym_month_farm.py` | IdealLoads calendar-month farm grow (structural) |
| `run_eplus_gym_month_live.py` | CLI-only closed-loop month (staged IdealLoads IDF) |
| `run_dsm_optimization_study.py` | Legacy scalar SCH_HtgSP study (prefer `vibe22.py`) |

## Twin foundation (live)

| Script | Role |
| --- | --- |
| `process_lakeside.py` | ALC → openfdd package |
| `demand_weather_charts.py` / `thermal_zone_analytics.py` | Site analytics |
| `eplus_observed_targets.py` | BAS→E+ targets |
| `eplus_gl14.py` / `eplus_campaign*.py` / `eplus_calibrate_multires.py` | IdealLoads G14 |
| `eplus_w2a_plant_calib.py` / `eplus_w2a_peak_monthly_dial.py` | W2A dial (never overwrite A04) |
| `eplus_heating_dsm_farm.py` | Paired IdealLoads farm (feeds gym **lookup**) |
| `eplus_w2a_dsm_farm_scaffold.py` | Stage W2A copy (no champion overwrite) |
| `export_control_contracts.py` | Strategy contracts for gym controllers |
| `validate_mvm.py` / `validate_eplus_multires.py` | Multi-res validation |
| `ingest_utility_bills.py` | Utility G14 inputs |

## Removed

- Streamlit UI → `archive/streamlit_ui_2026-08-13/`
- Hybrid ONNX / greybox / control-twin lab → **purged** (not in tree)
