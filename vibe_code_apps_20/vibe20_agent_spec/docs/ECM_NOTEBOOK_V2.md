# ECM Notebook v2 — sheet map and agent contract

**Audience:** Cursor / product agents building WattLab ECM Excel notebooks.

**Privacy (hard rule):**
- Never commit `calculators.zip`, client workbooks, client names, or bill CSVs to git / GH.
- Proprietary calculator reference (inspiration only) lives at
  `wattlab_workspace/private/reference/` — **gitignored**.
- Product math is WattLab-owned: `wattlab/bench/esco.py` + this notebook schema.
- Agents may *read* private reference locally; formulas written into notebooks must be
  independently rewritten WattLab expressions with provenance notes — never copy layouts,
  sheet names, or proprietary strings.

## Savings definition

| Layer | Meaning |
|-------|---------|
| **Baseline** | G14-calibrated Twin annual use (real when Twin attached) |
| **Measures (screening)** | WattLab ESCO/bin formulas or Python proxies |
| **Twin_Measures (target)** | `baseline_annual − ECM-on-Twin annual` when `savings_by_measure` exists |
| **Crosscheck** | Screening vs Twin — only when Twin rows exist |

Until BUG-048/049 cascade is fixed, Twin_Measures stays an honesty block.

## v2 sheet map (6 + slim agent sheets)

| Sheet | Purpose | Studio |
|-------|---------|--------|
| **Baseline** | Building label, Twin G14/EUI/kWh/therms, **Rates** (yellow named ranges) | Metrics + rates |
| **Measures** | Primary results table (cached numbers for Studio) | **Primary** |
| **Calc_Energy** | Live Excel energy formulas (`=` → Baseline named ranges) | Download only |
| **Calc_Cost** | Per-measure cost + payback + NPV formulas | Download only |
| **Twin_Measures** | E+ deltas or honesty note | Optional |
| **Crosscheck** | ESCO vs Twin (or stub) | Download only |
| **Charts** | Formula-linked bar charts — screening kWh, $/yr, Twin % diff | Download only |
| Guardrails / Docs | Slim agent metadata | Expander |

Dropped vs v1: standalone Cover, Inputs, Screening_Results, ESCO_Calcs, EPlus_Results, Compare, ROI_Capital (content merged into Baseline / Measures / Calc_* / Twin_*).

## Measures row rules

- `method=excel_formula` — kWh/therms from evaluated `FORMULA_ESCO_*` at build (must match Calc_Energy).
- `method=python_proxy` — bin calculators via `estimate_proxy_savings`.
- `method=energyplus` — from Twin `savings_by_measure`.
- `method=scope_tbd` — cost-only / zero savings with honest note (sensors, OA damper until scoped).
- Costs from `default_model_for(measure_id)` — **never** full-package $/ft² per row.

## Charts sheet

Agent-filled **formula-linked** chart data (row 4 header) — engineers can trace every bar:

| Column | Formula source |
|--------|----------------|
| `screening_kwh` | `=ESCO_Calcs!B{n}` |
| `twin_kwh` | `=EPlus_Results!B{n}` (blank until cascade) |
| `pct_diff_twin_vs_screening` | `(Twin − Screening) / Screening` |
| `annual_usd` | `=Screening_Results!F{n}` |
| `payback_yr` | `=Screening_Results!H{n}` |

Embedded charts (openpyxl): screening kWh, annual $/yr; when Twin exists add clustered ESCO vs Twin and % diff column chart.

## Rebuild

```bash
docker exec -e WATTLAB_STUDIO_WORKSPACE=/data vibe20 \
  python /data/tools/agent_build_ecm_packages.py \
    --answers /data/reports/answers_building_100_geo.json \
    --prefix geo_b100 \
    --packages controls_first,schedules_economizer,plant_optimization,envelope_code \
    --fan-hp 80 --fresh --write-scenario

docker exec vibe20 python /data/tools/audit_ecm_notebook.py \
  --dir /data/reports/notebooks
```

## Fable gates (must pass)

1. No row shows full-building capital unless measure scope = whole building.
2. No two measures share identical kWh/therms unless catalog declares overlap.
3. Measures cached numbers match Calc_Energy eval (±0.1%) for formula rows.
4. Proprietary zip never in `git status`.
5. No client name / bill CSV in committed files.
