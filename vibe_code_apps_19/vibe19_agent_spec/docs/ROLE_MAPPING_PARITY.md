# Role mapping — Streamlit demo

Cookbook rules read **logical roles** (`oa_t`, `sat`, `fan_status`, …). CSV columns are mapped via YAML + aliases — no Haystack RDF / Oxigraph.

## Source of truth

- `app/role_map.py` — `ROLE_ALIASES`, `POINT_ROLE_CANONICAL`, `COL_PATTERN_ROLES`, `resolve_role()`
- `configs/role_map.yaml` (or nested multi-site mapping from the Streamlit wizard)
- Equipment `columns.csv` `point_role` when present

## Common roles

| Logical role | Typical CSV / alias examples |
| --- | --- |
| `oa_t` | outside_air_temp, oat, oa-t |
| `sat` | discharge_air_temp, discharge_air_temp_f |
| `rat` | return_air_temp, ra-t |
| `mat` | mixed_air_temp, mat |
| `sat_sp` | sat_sp, dat_reset, cooling_setpoint |
| `fan_cmd` | supply_fan_speed, fan_speed, fan_cmd |
| `fan_status` | fan_status, fan_proof (prefer over fan_cmd for gates) |
| `clg_valve_pct` | chw_valve, clg_valve, cooling_valve |
| `htg_valve_pct` | hw_valve, htg_valve, heating_valve |
| `oa_damper_pct` | oa_damper, outdoor_air_damper, ex_dmpr |
| `zone_t` | space_temp, zone_temp, spacetemp |
| `occ_mode` | occ_mode, occupancy, schedule |
| `chw_supply_t` / `chw_return_t` | chws, chwr |

## Trust order

1. Explicit role map entry for equipment
2. `columns.csv` `point_role`
3. Column-name pattern heuristics in `COL_PATTERN_ROLES`

See also: [`../../docs/HAYSTACK_LIKE_MAPPING_GUIDE.md`](../../docs/HAYSTACK_LIKE_MAPPING_GUIDE.md) (authoring shape only — not an RDF runtime).
