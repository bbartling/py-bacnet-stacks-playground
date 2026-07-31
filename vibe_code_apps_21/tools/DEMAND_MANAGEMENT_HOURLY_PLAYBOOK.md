# Demand-management hourly E+ portfolio (ideas + implemented)

Target ML / Unity twin question: **given today’s outdoor conditions, what happens
to hourly facility kW when we play with HVAC?**

Twin SoT: `geo_b100_dual_ahu_shape_ops11` (G14 PASS).  
**Multi-day farm (ML):** `tools/dm_hourly_farm.py` → `~/wattlab_workspace/reports/dm_hourly_farm/`  
**Seed July portfolio:** `tools/july_demand_profiles_eplus.py` → `reports/full_parity_july_demand/`.

## Multi-day farm (gaps-doc minimum)

```bash
# Real EnergyPlus (needs Docker Desktop + energyplus-mcp-dev)
python vibe_code_apps_21/tools/dm_hourly_farm.py --smoke
python vibe_code_apps_21/tools/dm_hourly_farm.py            # 40 days × core + 10 full

# If WSL/Docker is down — interim Unity shapes only (NOT calibrated E+)
python vibe_code_apps_21/tools/dm_hourly_farm.py --from-seed-proxy
python vibe_code_apps_21/ml/train_demand_hourly.py
```

Outputs: `dm_hourly_rows.parquet`, `farm_summary.json`, model
`~/wattlab_workspace/models/demand_hourly_v1.joblib` (status `CANDIDATE`).

Unity end goal: scrub strategy knobs → predict hourly kW via this surrogate (Flask later).
Re-run **without** `--from-seed-proxy` once Docker works before any `APPROVED` claim.

## Implemented cases (hot July weekday 14:00–16:00 unless noted)

| Label | Physics story | ML label idea |
| --- | --- | --- |
| `weekday_baseline` | operator Twin, no DR | control |
| `weekend_baseline` | Sat occupancy/fan | weekend prior |
| `weekday_loadshed_p5f` | Clg + DAT +5°F | shed_setpoint |
| `weekday_deadband_10f` | zone DB ~5→10°F | shed_deadband |
| `weekday_chiller_off` | CHW AvailabilityManager OFF | shed_plant |
| `weekday_hvac_off` | FanAvail + CHW OFF | shed_hvac_hard |
| `weekday_precool_shift` | −2°F Clg/DAT 06–12; +5°F Clg / −2.5°F Htg 12–18 | **load_shift** |
| `weekday_precool_chiller_off` | precool 06–12 + CHW OFF 14–16 | shift_then_plant_shed |

Track both **peak-window ΔkW (14–16)** and **shape**: morning kWh↑ vs afternoon kWh↓.

## Strong next cases (not yet coded — good ML farm axes)

1. **Precool depth sweep** — −1 / −2 / −3 / −4°F morning × same afternoon relax (thermal-mass sensitivity).
2. **DAT-only shed** — raise Dump DAT without zone SP (air-side vs zone comfort trade).
3. **Static-pressure / fan-power truncate** — lower DSP SP during peak (fan kW without plant kill).
4. **OA / economizer morning soak** — max OA when OA enthalpy helps, min OA during peak.
5. **Partial plant capacity** — chiller max PLR / one-chiller lock (softer than full OFF).
6. **Staggered zone shed** — AHU1 zones shed, AHU2 hold (spatial Unity story).
7. **Recovery rebound** — after 16:00 snap setpoints back; measure 16–18 rebound spike.
8. **Weather × DR grid** — same DR on cool / design / extreme July days (OAT is the daily setting the ML must condition on).
9. **Gas co-fire check** — summer HW accidental on during electric shed (penalty label).
10. **Lighting/plug curtail** — only if end-use meters exist; else keep HVAC-only honesty.

## ML synthetic-data contract (daily setting → hourly demand)

For each farm run emit one row per hour:

- **context:** OAT, RH, solar, dow, hour, occupied flag, holiday  
- **actions (controls knobs):** precool_f, relax_clg_f, deadband_f, chw_avail, fan_avail, dat_delta_f, dsp_delta  
- **targets:** `facility_kw`, optional `cooling_kw`, `fan_kw`, zone unmet / max zone T  
- **event labels:** `in_dr_window`, `strategy_id`, `shift_score = afternoon_kwh_delta − morning_kwh_delta`

Do **not** train only on annual kWh — the Unity DM twin needs the **hourly shape** under OA + HVAC actions.

## Excel product path

Behavioral oracle workbook: `ECM_FULL_PARITY.xlsx` (Demand tab).  
Product path long-term: **open-fdd PyPI** `ECMJob` — keep Demand / provenance / honesty sheets in the upstream sheet contract.
