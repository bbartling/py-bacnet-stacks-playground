---
name: wattlab-eplus-demand-hourly
description: >-
  Run EnergyPlus hourly demand-management sims (shed, deadband, plant/HVAC off,
  precool load-shift) on the G14 Twin and feed ML/Unity DM twins. Use EnergyPlus-MCP
  as the IDF inspect/modify helper. Triggers on: demand management, load shed,
  load shift, precool, deadband, DR window, hourly kW, july_demand_profiles,
  Unity demand twin, synthetic DM training data.
---

# EnergyPlus hourly demand management (MCP helper)

**Question the farm answers:** given today’s outdoor conditions, what is the
**hourly facility kW** when we change HVAC controls?

## Twin SoT

- Run: `geo_b100_dual_ahu_shape_ops11` (Building 100 dual-AHU, G14 PASS)
- IDF: `runs/.../model.idf` (also packaged under vibe21 `assets/twin_b100_ops11/`)
- AMY: `...__stage_in/amy.epw`

## Runner

```bash
docker exec vibe20 python /data/tools/july_demand_profiles_eplus.py --reuse-existing
# optional: --only weekday_precool_shift weekday_deadband_10f
```

Output: `reports/full_parity_july_demand/july_demand_profiles.json`  
Playbook: `tools/DEMAND_MANAGEMENT_HOURLY_PLAYBOOK.md`  
Unity massing: `tools/export_unity_twin_manifest.py`

## Implemented strategies

| Mode | Story |
| --- | --- |
| `setpoint_raise` | Clg + DAT +°F in window |
| `deadband_widen` | DB ~5→10°F cooling-biased + DAT follow |
| `chiller_off` | CHW AvailabilityManager OFF |
| `hvac_off` | FanAvail + CHW OFF |
| `precool_shift` | morning precool then afternoon DB relax (**load shift**) |
| `precool_chiller_off` | precool then plant OFF through peak |

## EnergyPlus-MCP role

Use `wattlab-energyplus-mcp` / `energyplus-mcp-dev` to:

1. **inspect** schedules, AvailabilityManagers, Dump DAT, FanAvail before patching
2. **modify** when adding new DR knobs (DSP truncate, OA soak, capacity limit)
3. **simulate** / validate `eplusout.csv` Electricity:Facility Hourly
4. confirm comfort/unmet hours if labeling soft vs hard shed

```bash
docker exec -e WATTLAB_STUDIO_WORKSPACE=/data \
  -e WATTLAB_HOST_WORKSPACE=$HOME/wattlab_workspace vibe20 \
  wattlab energyplus-ensure
```

## ML / Unity contract (keep narrow)

- **Context:** OAT/RH/solar/hour/dow/occupied  
- **Actions:** precool_f, relax_clg_f, deadband_f, chw_avail, fan_avail, dat_delta_f  
- **Target:** hourly `facility_kw` (+ optional cooling/fan kW, max zone T)  
- **Not in scope for DM twin v1:** annual ECM package savings, FDD classifiers, gas-led ECMs

Excel Demand tab oracle: `ECM_FULL_PARITY.xlsx`. Product Excel long-term = **open-fdd PyPI `ECMJob`**.
