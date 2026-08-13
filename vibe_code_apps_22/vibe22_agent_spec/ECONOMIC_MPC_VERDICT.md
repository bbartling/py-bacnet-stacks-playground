# Economic MPC screening — verification verdict

| Gate | Verdict |
| --- | --- |
| Simulator integrity (Phase 0 + Jan 26) | **READY** |
| Optimization screening (study CLI + artifacts) | **READY** (proposal-only) |
| Live BACnet | **NO-GO** (this PR / branch) |

Evidence:

- Jan 26 2026 live baseline: `sp_creekside/reports/eplus_gym/gates/jan26_2026_baseline/READY.json`
  - OAT MAE vs EPW ≈ 0.22 °C; 96 weather rows; 9+6 zones; champion hash unchanged
  - Low-airflow warnings present → plant-power ranking caution
- Smoke study: `.../optimization/econ_mpc_smoke_20260126/`
- Streamlit **Optimize Tomorrow** renders billing-floor cost equations via `st.latex`
- Legacy opt-start iteration quarantined (no Site Config / last_dsm_run / ECM mutation)

Scientific claim on all surfaces: **ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY**.
