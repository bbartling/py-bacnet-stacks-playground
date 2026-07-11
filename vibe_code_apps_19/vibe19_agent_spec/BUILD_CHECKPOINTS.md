# Build checkpoints — Streamlit App 19

App 19 is the **Streamlit + pandas** educational FDD demo. Production Open-FDD lives in a separate repo.

## Current (keep green)

- [x] `streamlit run streamlit_app.py` — Open FDD Vibe Coder
- [x] 50 cookbook rules + operational gates (`SKIPPED_EQUIPMENT_OFF`)
- [x] Building-folder browse + Haystack-like column map JSON (any building id)
- [x] Overview / Analytics: motor hours + mech-cooling OAT bins (**web OAT** default; CHW leave-temp fallback)
- [x] Plots: **rule validation cards** (all applicable rules) + plot focus (one Plotly) + sensor fault stats + one-click FDD DOCX
- [x] **Data Model** section + DOCX reports (`app/rule_card.py`, `app/docx_report.py`, `PLACE PLOT HERE`)
- [x] **RCx Plots** tab: prebuilt overlays (zone temps, AHU DATs, duct-static box, HW/CHW/CW scatters) + generic picker + outlier highlight
- [x] Sidebar: imperial/metric display, prefer web OAT, weekly occupancy calendar, CHW leave proof °F
- [x] Weather enrich: dewpoint from RH (Magnus), wet-bulb (Stull) in `app/weather_psychrometrics.py`
- [x] Rules: ECON-3 web free-cool + SAT≈SP; VAV-7 fixed/high flow; **CW-OPT-1** (replaced WX-2)
- [x] `scripts/csv_parity_check.py` — any building folder
- [x] `python -m pytest -q`

## Explicitly out of scope (do not re-add)

- FastAPI / Flask / Uvicorn product UI
- Haystack RDF / Oxigraph / SPARQL (`haystack_rdf/`)
- Old `fdd_app/` / `csv_fdd_dashboard/` static HTML dashboard
- `fdd_dashboard_model/` typed loaders (superseded by `app/data_loader.py`)
- Rust / DataFusion in this folder
