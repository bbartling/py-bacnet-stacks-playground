# Column → role JSON mapping (Haystack-like)

Portable mapping so Streamlit can auto-run the 50-rule cookbook without hand-editing every slider.

**CSVs are never rewritten.** Authors use **Project Haystack–style** JSON
(`siteRef`, `equip`, `device`, `equipType`, `points` like `discharge-air-temp`).
The app normalizes those to cookbook roles (`sat`, `zone_t`, …) for rules.

## Pipeline

1. Load any building folder (Browse… or path) — leave historian files as-is
2. Copy the filled LLM prompt from **Data & Mapping** (or Auto-build heuristics)
3. Paste/load returned Haystack JSON
4. Normalize → cookbook roles on each equip DataFrame
5. Run rules; missing points → `SKIPPED_MISSING_ROLES`

## Files

| Path | Role |
| --- | --- |
| `app/column_map_json.py` | Haystack↔cookbook normalize, LLM prompt, save/load |
| `docs/HAYSTACK_LIKE_MAPPING_GUIDE.md` | Point name table |
| `configs/*_column_map.json` | Per-building maps (demo may include `building_100_…`) |

## UI

Streamlit tab **Data & Mapping**:

- Load / upload JSON (Haystack or legacy cookbook)
- Auto-build from loaded CSVs (exports Haystack `equip`/`points`)
- Filled LLM prompt with Streamlit code-block copy + `.txt` download
