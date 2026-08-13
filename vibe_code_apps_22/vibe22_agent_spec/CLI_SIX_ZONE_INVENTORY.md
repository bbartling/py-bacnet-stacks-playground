# CLI six-zone inventory snapshot

- Branch: `fix/vibe22-site-config-dsm`
- Commit: `3c4c7120`
- Practice site: `C:\Users\ben\OneDrive\Desktop\testing\sp_creekside`
- Tutorial copied to `examples/six_zone_coordinate_descent_tutorial.py` (DOCUMENTATION ONLY)
- Champion: `lakeside_w2a_a04_dual_champion.idf` — shared DualSP `Lakeside_AllZones_Tstat Dual SP Control` → `SCH_HtgSP`
- Prior Jan26 gate: `reports/eplus_gym/gates/jan26_2026_baseline/`
- Prior smoke study: `reports/eplus_gym/optimization/econ_mpc_smoke_20260126/`

## Classification

| Kind | Paths |
| --- | --- |
| Streamlit UI | `eplus_gym_app/streamlit_app.py`, UI renderers in `dsm_console`/`site_config`/`optimize_tomorrow` |
| Mixed | `dsm_console` staging/KPIs, `site_config` load/save |
| Pure | `eplus_gym/*`, `eplus_native/*`, tariff/objective/optimize |
