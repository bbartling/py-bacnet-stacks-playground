# Agent prompt — Streamlit 50-rule pandas FDD demo

**Open-FDD (Rust/DataFusion):** `C:\Users\ben\Documents\open-fdd` — do **not** re-add Rust here.

## Mission

Maintain Vibe App 19 as an **educational Streamlit demo** with the **full 50-rule pandas cookbook**:

- `app/rules/cookbook_catalog.py` — rule definitions
- `app/rules/runner.py` — skip-on-missing-role execution
- `configs/rule_inventory.yaml` + `rule_defaults.yaml`
- `streamlit_app.py` — 8 tabs including Rule Inventory

## Hard rules

1. **50 canonical rules** — never silently omit; use `SKIPPED — missing roles: …`
2. **No Rust / DataFusion / FastAPI / Haystack**
3. **No client CSV in git** — `HVAC_DATA_ROOT` only
4. **`python -m pytest -q`** before done

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
- [docs/STREAMLIT_AGENT_SPEC.md](docs/STREAMLIT_AGENT_SPEC.md)
