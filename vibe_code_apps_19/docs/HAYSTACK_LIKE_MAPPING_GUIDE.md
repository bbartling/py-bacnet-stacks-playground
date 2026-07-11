# Haystack-like mapping guide (no RDF)

App 19 uses **Project Haystack–style names** for authoring column maps (`siteRef`, `equip`,
`device`, `equipType`, `points`). It does **not** run Haystack RDF / Oxigraph / SPARQL.

Internally, rules still use Open-FDD **cookbook roles** (`sat`, `zone_t`, …).
`app/column_map_json.py` translates Haystack point names → cookbook roles.

## IDs

| Entity | Haystack-like key | Example |
|--------|-------------------|---------|
| Site | `siteRef` | `campus_a` |
| Building | `building` (folder name) | `HQ_NORTH` (demo may be `BUILDING_100`) |
| Equipment / device | `equip.<id>` + `device` | `AHU_1`, `VAV_7` |
| Equip type | `equipType` | `ahu`, `vav`, `chwPlant`, `boiler`, `heatPump`, `weather` (`rtu` → cookbook `AHU`) |
| Point | `points.<haystack-name>` | `discharge-air-temp` → cookbook `sat` |
| Column | CSV header value | `discharge_air_temp_f` |

## Preferred point names

| Haystack-like point | Cookbook role |
|---------------------|---------------|
| `discharge-air-temp` | `sat` |
| `discharge-air-temp-sp` | `sat_sp` |
| `mixed-air-temp` | `mat` |
| `return-air-temp` | `rat` |
| `outside-air-temp` | `oa_t` |
| `outside-air-damper` | `oa_damper_pct` |
| `cooling-valve` / `heating-valve` | `clg_valve_pct` / `htg_valve_pct` (valve % — **not** mech-cooling OAT-bin proof) |
| `fan-cmd` / `fan-status` | `fan_cmd` / `fan_status` |
| `duct-static-pressure` (+ `-sp`) | `duct_static` / `duct_static_sp` |
| `zone-air-temp` | `zone_t` |
| `zone-airflow` | `zone_flow` |
| `damper` / `reheat-valve` | `damper_pct` / `reheat_valve_pct` |
| `chilled-water-supply-temp` | `chw_supply_t` |
| `chw-pump-status` / `chiller-status` | `chw_pump_status` / `chiller_status` (chiller plant mech-cooling proof) |
| `compressor-status` / `dx-stage` / `cool-stage` | `compressor_status` / `dx_stage` / `cool_stage` (AHU/HP DX mech-cooling proof) |
| `occupied` | `occ_mode` |

**Mech-cooling OAT bins:** map compressor / plant roles above — never treat `cooling-valve` alone as mechanical cooling.

## Mapping flow

1. Load any building folder (Browse… or path) → pandas DataFrames (timestamps → DatetimeIndex)
2. Author or Auto-build Haystack JSON (`equip` / `points`)
3. Normalize → cookbook `column_roles` on each equip
4. Run 50 rules; missing points → `SKIPPED_MISSING_ROLES`

## Example JSON

```json
{
  "version": 1,
  "siteRef": "campus_a",
  "building": "HQ_NORTH",
  "generated_by": "llm",
  "equip": {
    "AHU_1": {
      "equipType": "ahu",
      "device": "AHU_1",
      "points": {
        "discharge-air-temp": "discharge_air_temp_f",
        "outside-air-temp": "outside_air_temp_f"
      }
    }
  }
}
```

Legacy `equipment` / `column_roles` / short cookbook keys still load.

## Not in this app

No RDF graph, SPARQL, or Oxigraph — use Haystack-*like* JSON column maps only (`app/column_map_json.py`).

Packages may ship a root `column_map.json`; the loader validates it and surfaces
`has_column_map` / issue counts on the package report. Agents can also export a
`role_map_gap_report.csv` (mapped vs missing roles per equipment) from the Mapping
or Export tabs, or via `scripts/agent_afdd.py`.
