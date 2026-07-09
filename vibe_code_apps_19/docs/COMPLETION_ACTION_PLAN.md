# Completion action plan — Streamlit migration + Open-FDD port

Date: 2026-07-09  
Branch: `streamlit-pandas-demo-vibe19`

## Completed

| Task | Status |
| --- | --- |
| Open-FDD Rust/DataFusion port | Done @ `open-fdd` `1f402f26` |
| Remove Rust/SQL/FastAPI from Vibe19 | Done (`dc90725`) |
| Streamlit app + 8 tabs | Done |
| 50-rule pandas cookbook | Done (`531e064`) |
| Rule inventory + slider YAML | Done |
| SKIPPED-on-missing-roles contract | Done |
| pytest (118 tests) | Pass |
| BUILDING_100 batch validation | Done (0 errors) |
| Role map auto-enrich from columns.csv | Done (this commit) |

## Fixed in this pass

1. **Role mapping** — `columns.csv` `point_role` → canonical cookbook roles with column ranking (reduces BUILDING_100 SKIPPED count).
2. **Open-FDD Windows test** — `econ4_confirm_test.rs` path join fix (committed in `open-fdd`).
3. **Push** — both repos to GitHub.

## Optional follow-ups (not blocking)

| Item | Priority |
| --- | --- |
| Expand `configs/role_map.yaml` for all 48 BUILDING_100 equipment | Medium |
| Archive/stub stale `vibe19_agent_spec/` Rust docs | Low |
| Streamlit `cached_weather` without streamlit in CLI scripts | Low |
| Fix mojibake in generated `rule_inventory.yaml` descriptions | Low |

## Definition of done

All blocking items above are **complete**. Optional items deferred.
