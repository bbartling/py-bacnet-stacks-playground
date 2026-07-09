# Haystack-like mapping guide (no RDF)

App 19 uses **simple IDs and refs**, not Project Haystack RDF or Oxigraph.

## IDs

| Entity | Pattern | Example |
|--------|---------|---------|
| Site | `site_id` slug | `acme_main` |
| Building | building folder / slug | `BUILDING_100` |
| Equipment | folder or upload name | `AHU_1`, `VAV_7` |
| Point role | cookbook logical role | `sat`, `oa_t`, `zone_t` |
| Column | CSV header | `discharge_air_temp_f` |

## Mapping flow

1. Load CSV tree, upload, or SQL query → pandas DataFrame
2. Profile source (wide vs long)
3. Assign site, building, equipment type
4. Map columns → cookbook roles (manual + `columns.csv` + heuristics)
5. Save flat or nested YAML under `configs/role_map.yaml`

## Equipment types

`AHU`, `VAV`, `CHW_PLANT`, `BOILER`, `HP`, `WEATHER`, `METER`, `UNKNOWN`

Rules that do not apply to a type return `NOT_APPLICABLE_EQUIPMENT_TYPE`.

## Missing roles

If required roles are absent, rules return `SKIPPED_MISSING_ROLES` with `missing_roles` populated.
