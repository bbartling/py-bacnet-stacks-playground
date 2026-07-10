# Data-model driven vs hard-linked (App 19)

Prefer **logical roles** and package/role_map config over equipment-name heuristics.

## Already data-model driven

| Concern | Mechanism |
| --- | --- |
| Point → rule inputs | `role_map` / `columns.csv` / Haystack JSON → `apply_role_map` |
| Chiller weekly runtime | Roles `chw_pump_status`, `chw_pump_cmd`, optional `chw_pump_equipment` |
| Package layout | `openfdd_package_v1` manifest + folder names as equipment ids |
| Rule applicability | `CookbookRule.equipment_kinds` |
| Units display | `unit_system` + role unit map |

## Still heuristic (candidates to migrate)

| Hard link | Better model |
| --- | --- |
| `_equipment_plant_group` from id string (`AHU`, `CHILLER`, …) | `equipment_type` / `plant_group` on equipment attrs or role_map meta |
| Named pump regex (`hwp1_s`, `cwp1_s`) | Explicit `chw_pump_status` / per-pump roles in columns.csv |
| Supply vs return fan ranking | Always map `fan_status` → supply column in role_map |
| Weather folder name `weather` | Manifest `weather_path` field |
| Mech-cooling proof chain order | Per-equipment `cooling_proof` preference in session_config |

## Agent / preprocess rule

When packaging for Cloud: put designated pump points on the chiller CSV **or** set `chw_pump_equipment` + `chw_pump_status` in `session_config.json` so the app never guesses from `chiller_*_command`.
