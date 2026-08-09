# Pinned Lakeside / Creekside EnergyPlus twins

These IDFs are calibration champions copied from the site workspace
(`LAKESIDE_SITE_ROOT/eplus/…`). Full run archives and EPWs stay on the site
root — this folder is for **reproducibility and farm seeding**.

| File | Role |
| --- | --- |
| `lakeside_6zone_gshp_best.idf` | IdealLoads best vs **interval** monthly kWh |
| `lakeside_6zone_gshp_best_utility.idf` | IdealLoads best vs **utility bill** G14 |
| `lakeside_w2a_l22_lowbase_optstart_champion.idf` | W2A L22 low-base / opt-start pin |
| `lakeside_w2a_e20_l22_enhanced_champion.idf` | W2A **E20** prior dual (~271 kW / GL14) |
| `lakeside_w2a_a04_dual_champion.idf` | W2A **A04** current dual (~287 kW / GL14) |
| `best_scorecard.json` | Interval IdealLoads metrics |
| `best_scorecard_utility.json` | Utility IdealLoads metrics |
| `best_scorecard_a04_dual.json` | A04 knobs + peak + GL14 metrics |

## Honesty

- **IdealLoads** zones + heat/cool COP → site electric proxy (DSM farm seed).
- **W2A plant** pins are post-`ExpandObjects` GSHP/plant twins with live knobs
  (`eplus_native/w2a_plant_knobs.py`). **A04 ≠ IdealLoads util champion** —
  do not overwrite `*_best_utility.idf`.
- Geometry is rectangular program massing, not CAD.
- Interval G14 ≠ utility-billing G14; monthly GL14 ≠ interval/DSM GO.

## A04 dual champion (2026-08-09)

- Peak design day **2026-01-26** ≈ **287 kW** (utility billed demand ~285 kW)
- Utility monthly GL14 **pass** (NMBE ≈ +1.0%, CVRMSE ≈ 10.4%)
- Soft htg COP **4.5**, clg COP **4.8**, equip×0.60, lights×0.95
- Summer-out **Jun–Jul** only; **August in-session**
- Tutorial notebook: `notebooks/lakeside_eplus_gl14_vs_peak285.ipynb`

Campaign scripts prefer the **site** `eplus/` copy when present, else fall
back to these pinned files under `vibe_code_apps_22/models/eplus/`.
