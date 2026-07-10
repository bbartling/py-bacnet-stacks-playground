# Agent prompt — Streamlit 50-rule pandas FDD demo

**Open-FDD (Rust/DataFusion):** `C:\Users\ben\Documents\open-fdd` — do **not** re-add Rust here.

## Mission

Maintain Vibe App 19 as an **educational Streamlit demo** with the **full 50-rule pandas cookbook**:

- `app/rules/cookbook_catalog.py` — rule definitions
- `app/rules/runner.py` — skip / equipment-off / not-applicable execution
- `configs/rule_inventory.yaml` + `rule_defaults.yaml`
- `streamlit_app.py` — Overview, mapping, run rules, **Plots**, **RCx Plots**, analytics
- `app/rcx_plots.py` + `app/ui_rcx_tab.py` — multi-equipment RCx charts
- `app/weather_psychrometrics.py` — web OAT / dewpoint / wet-bulb

## Hard rules

1. **50 canonical rules** — never silently omit; use `SKIPPED_MISSING_ROLES`, `SKIPPED_EQUIPMENT_OFF`, or `NOT_APPLICABLE_EQUIPMENT_TYPE`
2. **No Rust / DataFusion / FastAPI / Flask / Haystack RDF / Oxigraph**
3. **No client CSV in git** — browse a local building folder only
4. **Do not recreate** `haystack_rdf/`, `fdd_app/`, `fdd_dashboard_model/`
5. **Web OAT by default** for analytics / free-cool weather path
6. **`python -m pytest -q`** before done
7. **Keep `vibe19_agent_spec/` in sync** after UI/plot/rule changes (`SESSION_LOG.md`, skills, checkpoints)

## Run

```powershell
cd vibe_code_apps_19
streamlit run streamlit_app.py
```

## Regenerate configs after catalog changes

```powershell
python scripts/generate_rule_configs.py
```

## Specs

- [vibe19_agent_spec/AGENTS.md](vibe19_agent_spec/AGENTS.md)
- [vibe19_agent_spec/docs/RCX_PLOTS.md](vibe19_agent_spec/docs/RCX_PLOTS.md)
- [docs/STREAMLIT_RULE_INVENTORY.md](docs/STREAMLIT_RULE_INVENTORY.md)
- [vibe19_agent_spec/docs/OPERATIONAL_GATES.md](vibe19_agent_spec/docs/OPERATIONAL_GATES.md)
- [docs/HAYSTACK_LIKE_MAPPING_GUIDE.md](docs/HAYSTACK_LIKE_MAPPING_GUIDE.md)
