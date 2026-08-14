---
name: lakeside-optstart-iteration
description: >-
  INVALID / LEGACY DIAGNOSTIC ONLY. Do not use for ranking, ECM publish, or
  Site Config promotion. Superseded by skills/eplus-economic-mpc.
---

# INVALID — Lakeside optimum-start iteration (legacy)

**Status: INVALID / LEGACY DIAGNOSTIC — do not use for operational decisions.**

This skill and `scripts/iterate_optstart_lakeside.py` are quarantined because:

1. **Sizing-day contamination** — staged IDFs could run sizing periods
   (`kind_of_sim != 3`), and trajectory dating used synthetic `step//96` days.
2. **Illustrative tariff** — fixed \$0.12/kWh + \$15/kW applied as if verified.
3. **Wrong control semantics** — “opt-start” advanced fan/OA only; `SCH_HtgSP`
   recovery was never parametric.
4. **Auto-promote** — wrote Site Config / `last_dsm_run` / ECM without proposal gate.

Historical folders under `{SITE}/reports/eplus_gym/runs/*_optstart_iter/` and
`optstart_iteration_summary.json` must carry `INVALID.md` / invalid flags and
**must not** rank candidates or publish ECMs.

Use **`skills/eplus-economic-mpc/SKILL.md`** instead (PHYSICAL_ONLY billing floor,
parametric heating recovery, recommendation-only artifacts).
