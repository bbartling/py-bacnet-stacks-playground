# vibe22 scripts map

**Product SoT (2026-08-11):** [`eplus_gym`](../eplus_gym/) + human DSM console.  
Agent loop: [`../vibe22_agent_spec/AGENT_LOOP.md`](../vibe22_agent_spec/AGENT_LOOP.md).  
Archived hybrid/greybox/lab scripts: [`../archive/2026-08-10_pre_eplus_gym/scripts/`](../archive/2026-08-10_pre_eplus_gym/scripts/).

## Product

| Script | Role |
| --- | --- |
| `ingest_site_pack.py` | Zip/folder → site layout + `site_ui_bundle_v1.json` |
| `run_eplus_gym_rules.py` | Rule DR (`--family w2a\|idealloads`, `lookup` / `live` / `auto`) |
| `run_eplus_gym_month_farm.py` | IdealLoads calendar-month farm grow (structural) |
| `run_eplus_gym_month_live.py` | CLI-only closed-loop month (staged IdealLoads IDF) |

UI: `streamlit run eplus_gym_app/streamlit_app.py --server.port 8765`

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
| `build_real_15min_store.py` | Real BAS parquet (site analytics) |
| `export_control_contracts.py` | Strategy contracts for gym controllers |
| `validate_mvm.py` / `validate_eplus_multires.py` | Multi-res validation |
| `ingest_utility_bills.py` | Utility G14 inputs |

## Removed from live tree (archived)

`train_four_arms`, `ship_best_to_desktop`, `promote_hybrid_ship`, greybox trainers,
`run_control_twin_lab`, notebook generators, one-off W2A dial helpers — see archive.
