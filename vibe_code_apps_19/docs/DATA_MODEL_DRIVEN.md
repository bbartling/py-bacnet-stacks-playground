# Data-model driven vs hard-linked (App 19)

Prefer **Haystack point names** and package / column-map config over equipment-name heuristics.

## Typed equipment is canonical

Resolver: `app.site_model.resolve_equipment_type` / `stamp_equipment_type`.

| Priority | Source |
| --- | --- |
| 1 | `df.attrs["equipment_type"]` (stamped on load) |
| 2 | role_map / site / column_map `equipment_type` or `equipType` |
| 3 | `equipment_type_from_id` (id substring) — **fallback only** |

**Normalize:** `heatPump` / `HEAT_PUMP` → `HP`; `RTU` / rooftop → `AHU` (use DX points for mechanical cooling). Agents must stamp `equipType` in `column_map.json` so rules/analytics/RCx do not guess from folder names.

Cookbook kinds (`infer_equipment_kind`) and RCx membership use the resolved type — **no id-substring membership** in `collect_oat_scatter` / `collect_role_series`.

## Already data-model driven

| Concern | Mechanism |
| --- | --- |
| Point → rule inputs | Haystack JSON / `role_map` / `columns.csv` → `apply_role_map` |
| Equipment type | `resolve_equipment_type` (attrs → map → id) |
| Chiller weekly runtime | Points `chw-pump-status`, `chw-pump-cmd`, optional `chw_pump_equipment` |
| Motor weekly series | Mapped `fan-*` / `chw-pump-*` / `hw-pump-*` / `pump-*` before named-pump regex |
| Package layout | `openfdd_package_v1` manifest + folder names as equipment ids |
| Rule applicability | `CookbookRule.equipment_kinds` via resolved type |
| Units display | `unit_system` + point unit map |
| Mech-cooling OAT bins | Compressor / plant points only — see below |
| RCx preset membership | Resolved `equipment_type` + point-based series |
| AHU↔VAV topology | `vav_to_ahu_simple.csv` → Data Model Topology section |

## Mechanical cooling proof points (OAT bins)

**Counts as mechanical cooling** (`app/analytics.py`):

| Equipment | Points (first match wins) |
| --- | --- |
| Chiller / CHW plant | `chw-pump-status`, `pump-status`, `chw-pump-cmd`, `pump-cmd` → then `chiller-status`, `compressor-status`, `equipment-enable` → then `chiller-amps` / `chiller-power` |
| AHU with DX (incl. RTU-as-AHU) | `compressor-status`, `dx-cool-cmd`, `dx-cooling`, `cool-stage`, `dx-stage` |

Never use `cooling-valve` / CHW valve % alone as mech-cooling proof.

## Topology

VAV **fedBy** parent AHU; AHU **feeds** VAV children. Source: package
`vav_to_ahu_simple.csv` (never invented). Parent AHU `discharge-air-temp` may be
copied onto each VAV as `ahu-discharge-air-temp` for cross-equip rules.
