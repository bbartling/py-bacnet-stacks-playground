# Initial Schemas — Vibe 21

This file defines conceptual JSON shapes. Implementation may use Pydantic, dataclasses, TypedDict, JSON Schema, or equivalent, but wire semantics and versions must remain explicit.

**DM twin priority schema:** `vibe21.dm_hourly_row.v2` (section 0). Broader twin/scenario schemas below remain available but are secondary.

## 0. Demand-management hourly training row

Additive twin I/O targets (AHU/plant/zone) on top of DR knobs + `facility_kw`.
Terminal VAV damper positions are intentionally omitted in v2 (optional v2.1).

```json
{
  "schema_version": "vibe21.dm_hourly_row.v2",
  "simulation_id": "ops11_2025-07-24_precool_shift",
  "twin_run_id": "geo_b100_dual_ahu_shape_ops11",
  "day": "2025-07-24",
  "hour_ending": 15,
  "dow": "Thursday",
  "oat_c": 35.1,
  "rh_pct": 42.0,
  "ghi": 780.0,
  "occupied": true,
  "strategy_id": "precool_shift",
  "phase": "relax",
  "actions": {
    "precool_f": 2.0,
    "relax_clg_f": 5.0,
    "relax_htg_f": 2.5,
    "deadband_target_f": null,
    "dat_delta_f": 5.0,
    "chw_avail": 1.0,
    "fan_avail": 1.0
  },
  "targets": {
    "facility_kw": 441.5,
    "cooling_kw": 180.2,
    "zone_temp_ahu1_mean_c": 24.1,
    "zone_temp_ahu2_mean_c": 24.4,
    "max_zone_temp_c": 25.2,
    "ahu1_dat_c": 12.8,
    "ahu1_mix_c": 23.5,
    "ahu1_ra_c": 24.0,
    "ahu1_oa_c": 35.0,
    "ahu1_fan_plr": 0.72,
    "ahu1_oa_frac": 0.25,
    "ahu2_dat_c": 12.5,
    "ahu2_mix_c": 23.8,
    "ahu2_ra_c": 24.2,
    "ahu2_oa_c": 35.0,
    "ahu2_fan_plr": 0.68,
    "ahu2_oa_frac": 0.22,
    "chw_supply_c": 6.7,
    "chw_return_c": 12.1,
    "chw_pump_plr": 1.0,
    "cw_pump_plr": 0.85,
    "tower_fan_plr": 0.6,
    "tower_leaving_c": 29.4,
    "unmet_hours_flag": false
  },
  "provenance": {
    "source": "ENERGYPLUS_SIMULATED",
    "idf_sha256": "...",
    "epw": "amy.epw"
  }
}
```

Legacy `vibe21.dm_hourly_row.v1` rows remain readable; trainers prefer v2 columns when present.

### Farm commands

```text
# Pilot (~15 sims) — turnkey multi-target path
python tools/dm_hourly_farm.py --pilot --engine native

# Full overnight farm (~190 sims)
python tools/dm_hourly_farm.py --engine native --n-days 40 --n-full 10
```

## 1. Twin manifest

```json
{
  "schema_version": "vibe21.twin_manifest.v1",
  "building_id": "bldg_building_100",
  "display_name": "Building 100",
  "source_status": {
    "vibe19": "AVAILABLE",
    "vibe20": "MONTHLY_CALIBRATED",
    "ml_bundle": "APPROVED_DEMO"
  },
  "feature_schema_version": "vibe21.features.operational.v1",
  "scenario_schema_version": "vibe21.features.scenario.v1",
  "model_registry_version": "vibe21.model_registry.v1",
  "unity_binding_version": "vibe21.unity_binding.v1"
}
```

## 2. Model registry

```json
{
  "schema_version": "vibe21.model_registry.v1",
  "models": [
    {
      "model_id": "demand_now_v1",
      "family": "OPERATIONAL_DEMAND",
      "artifact": "models/demand_now.joblib",
      "artifact_sha256": "...",
      "status": "APPROVED_DEMO",
      "targets": ["building_kw_avg_interval"],
      "feature_schema_version": "vibe21.features.operational.v1",
      "training_dataset_sha256": "...",
      "training_source": "ENERGYPLUS_SIMULATED_PLUS_OPTIONAL_BAS_VALIDATION",
      "sklearn_version": "recorded-at-build",
      "metrics": {
        "synthetic_test": {},
        "real_holdout": {}
      }
    }
  ]
}
```

## 3. Operational feature request

```json
{
  "schema_version": "vibe21.predict_operational.v1",
  "building_id": "bldg_building_100",
  "model_id": "demand_now_v1",
  "interval_minutes": 15,
  "history": []
}
```

## 4. Operational prediction

```json
{
  "schema_version": "vibe21.prediction.v1",
  "building_id": "bldg_building_100",
  "model_id": "demand_now_v1",
  "model_version": "1.0.0",
  "prediction_timestamp_utc": "2026-07-25T12:15:00Z",
  "predicted_kw": 425.3,
  "derived_interval_kwh": 106.325,
  "interval_minutes": 15,
  "domain_status": "IN_DOMAIN",
  "feature_coverage": 1.0,
  "warnings": [],
  "provenance": {
    "kind": "ML_SURROGATE",
    "physics_source": "ENERGYPLUS",
    "training_manifest": "training_manifest.json"
  }
}
```

## 5. Scenario prediction request

```json
{
  "schema_version": "vibe21.predict_scenario.v1",
  "building_id": "bldg_building_100",
  "scenario_id": "interactive_preview",
  "features": {
    "weather_id": "amy_2025",
    "cooling_capacity_multiplier": 0.8,
    "fan_power_multiplier": 1.0,
    "outdoor_air_fraction": 0.1,
    "economizer_enabled": false,
    "occupied_start_hour": 6.0,
    "occupied_end_hour": 19.0,
    "cooling_setpoint_f": 74.0
  }
}
```

## 6. Scenario prediction response

```json
{
  "schema_version": "vibe21.scenario_prediction.v1",
  "building_id": "bldg_building_100",
  "scenario_id": "interactive_preview",
  "model_bundle_id": "scenario_surrogate_v1",
  "outputs": {
    "annual_electricity_kwh": 1425000.0,
    "peak_electric_demand_kw": 612.4,
    "annual_natural_gas_therm": 18400.0,
    "unmet_hours": 213.0
  },
  "domain_status": "IN_DOMAIN",
  "warnings": [],
  "prediction_kind": "ML_SURROGATE_OF_ENERGYPLUS"
}
```

## 7. Dataset manifest

```json
{
  "schema_version": "vibe21.dataset_manifest.v1",
  "dataset_id": "b100_synthetic_operational_v1",
  "building_id": "bldg_building_100",
  "physics_model_id": "eplus_b100_calibrated_v3",
  "physics_model_status": "MONTHLY_CALIBRATED",
  "row_grid_minutes": 15,
  "simulation_count": 10000,
  "row_count": 0,
  "feature_schema_version": "vibe21.features.operational.v1",
  "target_schema_version": "vibe21.targets.operational.v1",
  "scenario_manifest_sha256": "...",
  "dataset_sha256": "...",
  "created_at": "ISO-8601"
}
```

## 8. Training manifest

```json
{
  "schema_version": "vibe21.training_manifest.v1",
  "training_run_id": "train_...",
  "dataset_id": "b100_synthetic_operational_v1",
  "dataset_sha256": "...",
  "feature_compiler_version": "1.0.0",
  "split_strategy": {
    "kind": "GROUPED_SIMULATION_HOLDOUT",
    "group_column": "simulation_id",
    "train_fraction": 0.7,
    "validation_fraction": 0.15,
    "test_fraction": 0.15
  },
  "candidates": [],
  "champion_model_id": "demand_now_v1",
  "source_commit": "git-sha",
  "python_version": "recorded",
  "sklearn_version": "recorded"
}
```

## 9. Unity binding

```json
{
  "schema_version": "vibe21.unity_binding.v1",
  "unity_object_key": "Building100/Floor2/VAV_7",
  "entity_type": "equipment",
  "entity_id": "equip_vav_7",
  "source_refs": {
    "vibe19_equipment_id": "VAV_7",
    "energyplus_object": "AirTerminal:SingleDuct:VAV:Reheat VAV_7"
  },
  "supported_visual_modes": [
    "comfort",
    "fault",
    "predicted_load"
  ]
}
```

## 10. Status enums

Suggested statuses:

```text
READY
NEEDS_INPUT
NEEDS_ENGINEERING_REVIEW
CONCEPTUAL_ONLY
MONTHLY_CALIBRATED
VALIDATED
EXPERIMENTAL
VALIDATED_SYNTHETIC
VALIDATED_REAL_HOLDOUT
APPROVED_DEMO
OUT_OF_TRAINING_DOMAIN
MODEL_LOAD_FAILED
PREDICTION_FAILED
```
