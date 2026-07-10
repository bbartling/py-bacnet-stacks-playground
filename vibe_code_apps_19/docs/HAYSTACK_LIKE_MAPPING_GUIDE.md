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
| Equip type | `equipType` | `ahu`, `vav`, `chwPlant`, `boiler`, `heatPump`, `weather` |
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
| `cooling-valve` / `heating-valve` | `clg_valve_pct` / `htg_valve_pct` |
| `fan-cmd` / `fan-status` | `fan_cmd` / `fan_status` |
| `duct-static-pressure` (+ `-sp`) | `duct_static` / `duct_static_sp` |
| `zone-air-temp` | `zone_t` |
| `zone-airflow` | `zone_flow` |
| `damper` / `reheat-valve` | `damper_pct` / `reheat_valve_pct` |
| `chilled-water-supply-temp` | `chw_supply_t` |
| `occupied` | `occ_mode` |

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

No RDF graph, SPARQL, or Oxigraph — see retired skill `vibe19-haystack-rdf`.
