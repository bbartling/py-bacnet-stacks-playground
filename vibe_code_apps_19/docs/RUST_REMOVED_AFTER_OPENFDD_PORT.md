# Rust removed after Open-FDD port

Date: 2026-07-09  
Branch: `streamlit-pandas-demo-vibe19`

## Verification

Open-FDD repo `C:\Users\ben\Documents\open-fdd`:

- Branch `port-vibe19-rust-datafusion-engine`
- `cargo test --workspace` passes
- BUILDING_100 parity benchmark 368/0 @ 0.5h tolerance

## Removed from Vibe App 19

| Path | Notes |
| --- | --- |
| `rust_fdd_core/` | Entire Rust workspace |
| `sql_rules/` | DataFusion SQL templates |
| `rule_tuning/` | SQL registry tuning YAML |
| `haystack_rdf/` | Oxigraph/Haystack RDF layer |
| `fdd_app/` | FastAPI + static dashboard |
| `fdd_dashboard_model/` | Old typed dashboard loaders |
| Rust CI / Docker deploy files | Replaced by Streamlit `pyproject.toml` |

## Replaced by

- `streamlit_app.py` — UI
- `app/` — loaders, rules, charts, reports
- `configs/` — demo defaults
- `docs/STREAMLIT_*.md` — specs

## If you need Rust/SQL parity again

Use Open-FDD — do not copy Rust back into this repo without an explicit decision to merge architectures.
