# Data-model driven vs hard-linked (App 19)

Prefer **logical roles** and package/role_map config over equipment-name heuristics.

## Typed equipment is canonical

Resolver: `app.site_model.resolve_equipment_type` / `stamp_equipment_type`.

| Priority | Source |
| --- | --- |
| 1 | `df.attrs["equipment_type"]` (stamped on load) |
| 2 | role_map / site / column_map `equipment_type` or `equipType` |
| 3 | `equipment_type_from_id` (id substring) — **fallback only** |

**Normalize:** `heatPump` / `HEAT_PUMP` → `HP`; `RTU` / rooftop → `AHU` (use DX roles for mechanical cooling). Agents must stamp `equipType` in `column_map.json` so rules/analytics/RCx do not guess from folder names.

Cookbook kinds (`infer_equipment_kind`) and RCx membership use the resolved type — **no id-substring membership** in `collect_oat_scatter` / `collect_role_series`.

## Already data-model driven

| Concern | Mechanism |
| --- | --- |
| Point → rule inputs | `role_map` / `columns.csv` / Haystack JSON → `apply_role_map` |
| Equipment type | `resolve_equipment_type` (attrs → map → id) |
| Chiller weekly runtime | Roles `chw_pump_status`, `chw_pump_cmd`, optional `chw_pump_equipment` |
| Motor weekly series | Mapped `fan_*` / `chw_pump_*` / `hw_pump_*` / `pump_*` before named-pump regex |
| Package layout | `openfdd_package_v1` manifest + folder names as equipment ids |
| Rule applicability | `CookbookRule.equipment_kinds` via resolved type |
| Units display | `unit_system` + role unit map |
| Mech-cooling OAT bins | Compressor / plant roles only — see below |
| RCx preset membership | Resolved `equipment_type` + role-based series |

## Mechanical cooling proof roles (OAT bins)

**Counts as mechanical cooling** (`app/analytics.py`):

| Equipment | Roles (first match wins) |
| --- | --- |
| Chiller / CHW plant | `chw_pump_status`, `pump_status`, `chw_pump_cmd`, `pump_cmd` → then `chiller_status`, `compressor_status`, `equipment_enable` → then `chiller_amps` / `chiller_power_kw` |
| AHU with DX (incl. RTU-as-AHU) | `compressor_status`, `dx_cool_cmd`, `dx_cooling`, `cool_stage`, `dx_stage` |
| Heat pump (`HP`) | same DX roles + `compressor_status` |

**Never counts:** `clg_valve_pct`, `cooling_valve`, `chw_valve`, or any AHU chilled-water valve % alone. Session flag `include_ahu_chw_valve` is **deprecated and ignored** (always false).

## Motor / plant charts (roles first)

`discover_plant_motor_series`:

1. Plant group from `attrs` / role_map `plant_group` → typed equip → id fallback
2. Prefer mapped fan/pump roles
3. Named-pump regex (`hwp1_s`, `cwp1_s`) only when pump roles empty; tower motors still discovered
4. Empty fan roles + agent map → **omit** supply-fan series (do not invent from raw `supply_*` columns)

## Still heuristic (narrow)

| Hard link | When used |
| --- | --- |
| Named pump / tower column regex | Only if no mapped pump roles |
| `suggest_roles` column-name fill | Only when no explicit map or motor roles empty |
| Weather folder name `weather` | Prefer manifest `weather_path` when present |

## Agent / preprocess rule

When packaging for Cloud/Docker (YouTube demos: **500 MB** zip default):

1. Stamp **`equipType`** / `equipment_type` on every equip in `column_map.json`
2. Map designated pumps / fans / DX compressors — never invent runtime from leave temp or valve %
3. Put designated pump points on the chiller CSV **or** set `chw_pump_equipment` + `chw_pump_status` in `session_config.json` / role_map meta
4. Session config round-trips `equipment_type` (and optional `plant_group` / `chw_pump_equipment`) via role_map meta keys
