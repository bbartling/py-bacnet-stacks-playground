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
| `clg_valve_pct` | chw_valve, clg_valve, cooling_valve — **FDD/control only; never mech-cooling OAT bins** |
| `htg_valve_pct` | hw_valve, htg_valve, heating_valve |
| `oa_damper_pct` | oa_damper, outdoor_air_damper, ex_dmpr |
| `zone_t` | space_temp, zone_temp, spacetemp |
| `occ_mode` | occ_mode, occupancy, schedule (also Overview calendar → always applied) |
| `chw_supply_t` / `chw_return_t` | chws, chwr |
| `chw_pump_status` / `chw_pump_cmd` | Designated CHW pump for **weekly motor / plant circulation** hours only — **not** mech-cooling OAT-bin compressor proof |
| `chiller_status` / `compressor_status` / amps / power | Chiller/compressor proof for mech-cooling OAT bins |
| `compressor_status` / `dx_stage` / `dx_cool_cmd` / `cool_stage` | AHU/HP/RTU DX compressor proof for mech-cooling OAT bins |

## Mech-cooling OAT bins (do not confuse with valves or pumps)

Mechanical cooling charts require a **compressor device**:

- Chiller plant: chiller/compressor **status** → verified **command** → amps/power (see [`ANALYTICS.md`](ANALYTICS.md))
- AHU / heat pump / RTU: DX / compressor roles above
- **Not** `chw_pump_status` / `chw_pump_cmd` alone — pumps are motor evidence
- **Not** `clg_valve_pct` — valves often open with no chilled water / no compressor

See [`../../docs/DATA_MODEL_DRIVEN.md`](../../docs/DATA_MODEL_DRIVEN.md) and [`../../docs/PACKAGE_SPEC.md`](../../docs/PACKAGE_SPEC.md).

## Trust order

1. Explicit role map entry for equipment
2. `columns.csv` `point_role`
3. Column-name pattern heuristics in `COL_PATTERN_ROLES`

See also: [`../../docs/HAYSTACK_LIKE_MAPPING_GUIDE.md`](../../docs/HAYSTACK_LIKE_MAPPING_GUIDE.md) (authoring shape only — not an RDF runtime).
