# A04 continuous 68°F monthly vs utility bills

**Claim:** `CONTINUOUS_68_REFERENCE` — not an operational DSM baseline. Heating DualSP held at **68°F** (20°C) 24/7 on staged `DSM_HTG_SP_*` schedules via EnergyPlus CLI (coexists with concurrent Gym RL).

**Model:** `models/eplus/lakeside_w2a_a04_dual_champion.idf`  
**Period:** 2025-08 … 2026-05 (overlap with site utility CSV + AMY EPW)  
**Utility:** `$SITE_ROOT/utilities/electricity_utility_demand.csv`  
**Sim costs:** ILLUSTRATIVE `FLAT_PLUS_DEMAND` ($0.11/kWh + $12/kW) — not verified utility pricing. Actual bill `cost_usd` plotted separately.

## Artifacts (this folder)

| File | Content |
| --- | --- |
| `monthly_continuous68_vs_utility.csv` | Monthly sim peak/kWh/illustrative cost vs utility |
| `monthly_kwh_continuous68_vs_utility.png` | kWh line chart |
| `monthly_peak_kw_continuous68_vs_utility.png` | Peak kW line chart |
| `monthly_cost_continuous68_ill_vs_actual_bill.png` | Illustrative sim $ vs actual bill $ |
| `monthly_cost_continuous68_vs_utility_repriced_ill.png` | Same illustrative tariff on sim vs utility kWh+billed demand |
| `manifest.json` | Provenance |

## Runner

```text
python scripts/a04_continuous68_monthly_utility_compare.py --site-root $SITE_ROOT
```

Raw `eplus_out/` stays under `$SITE_ROOT/reports/...` (not committed).
