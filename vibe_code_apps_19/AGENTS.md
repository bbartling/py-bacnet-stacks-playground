# Agent prompt — Streamlit 50-rule pandas FDD demo

**Open-FDD (Rust/DataFusion):** `C:\Users\ben\Documents\open-fdd` — do **not** re-add Rust here.

## Mission

Maintain Vibe App 19 as an **educational Streamlit demo** with the **full 50-rule pandas cookbook**:

- `app/rules/cookbook_catalog.py` — rule definitions
- `app/rules/runner.py` — explicit skip / not-applicable execution
- `configs/rule_inventory.yaml` + `rule_defaults.yaml`
- `streamlit_app.py` — tabs including Site Mapping, multi-CSV, SQL inputs

## Hard rules

1. **50 canonical rules** — never silently omit; use `SKIPPED_MISSING_ROLES` or `NOT_APPLICABLE_EQUIPMENT_TYPE`
2. **No Rust / DataFusion / FastAPI / Haystack RDF**
3. **No client CSV in git** — `HVAC_DATA_ROOT` only
4. **SQL is input-only** (pandas DataFrames), not production FDD
5. **`python -m pytest -q`** before done

## Run

```bash
streamlit run streamlit_app.py
```

## Regenerate configs after catalog changes

```bash
python scripts/generate_rule_configs.py
```

## Specs

- [docs/STREAMLIT_RULE_INVENTORY.md](docs/STREAMLIT_RULE_INVENTORY.md)
- [docs/MULTI_SITE_CSV_SQL_SPEC.md](docs/MULTI_SITE_CSV_SQL_SPEC.md)
- [docs/STREAMLIT_AGENT_SPEC.md](docs/STREAMLIT_AGENT_SPEC.md)
