---
name: eplus-economic-mpc
description: >-
  EnergyPlus Gym economic DSM optimization screening (retrospective AMY replay).
  PHYSICAL_ONLY billing-floor objective, parametric SCH_HtgSP recovery, proposal-only
  recommendations. Never BACnet / never auto-promote Site Config.
---

# EnergyPlus Economic MPC (screening)

**Claim:** ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY.
Not operational MPC. Not verified savings. Not live BACnet.

## Cost equations (billing floor)

\[
C = C_{\mathrm{energy}} + C_{\mathrm{demand}}^{\mathrm{inc}}
\]

\[
C_{\mathrm{energy}} = \sum_{t=1}^{96} P_t\,\Delta t\, r_{\mathrm{energy}}(t)
\quad(\Delta t=0.25\,\mathrm{h})
\]

\[
P^{\mathrm{new}}=\max(P^{\mathrm{MTD}}, P^{\mathrm{day}}),\quad
\Delta P=\max(0, P^{\mathrm{new}}-P^{\mathrm{MTD}}),\quad
C_{\mathrm{demand}}^{\mathrm{inc}}=\Delta P\, r_{\mathrm{demand}}
\]

Default **PHYSICAL_ONLY**: rank by energy / peak / comfort — illustrative $ never
selects a winner. Streamlit **Optimize Tomorrow** renders these via `st.latex`.

## Workflow

1. Phase 0 integrity: staged IDF `Sizing Periods=No`; `kind_of_sim==3`; Runtime dates.
2. Parametric controller: `eplus_gym/parametric_daily_controller.py`.
3. Study CLI: `scripts/run_dsm_optimization_study.py` →
   `{SITE}/reports/eplus_gym/optimization/<study_id>/`.
4. UI approve → `approved_recommendation.json` only.

## Forbidden

- Mutate `site_dsm_config.json`, `last_dsm_run.json`, published ECM, champion IDF.
- Trust legacy `skills/lakeside-optstart-iteration` (INVALID).
- Live BACnet writes.
