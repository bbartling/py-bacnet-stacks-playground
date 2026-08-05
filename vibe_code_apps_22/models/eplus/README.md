# Pinned Lakeside EnergyPlus twins (IdealLoads + COP proxy)

These IDFs are the **G14-passing** calibration champions copied from the site
workspace (`LAKESIDE_SITE_ROOT/eplus/models/`). Full run archives and EPWs stay
on the site root — this folder is for **reproducibility and farm seeding**.

| File | Role |
| --- | --- |
| `lakeside_6zone_gshp_best.idf` | Best vs **interval** monthly kWh (iter_78) |
| `lakeside_6zone_gshp_best_utility.idf` | Best vs **utility bill** G14 |
| `best_scorecard.json` | Interval champion metrics |
| `best_scorecard_utility.json` | Utility champion metrics |

## Honesty

- **IdealLoads zones + heat/cool COP → site electric proxy**, not a full
  water-to-air HP + GLHE plant.
- Geometry is rectangular program massing, not CAD.
- Interval G14 (NMBE / CVRMSE) ≠ utility-billing G14.
- Use these as seeds for heating DSM EnergyPlus farms (`scripts/eplus_heating_dsm_farm.py`).

## Interval G14 (best_scorecard.json)

- Status: **pass** (`iter_78`)
- NMBE ≈ −3.3%, CVRMSE ≈ 12.1% (ASHRAE G14 monthly electric gates)
- Heat COP proxy 3.5 / cool COP proxy 4.5

Campaign scripts prefer the **site** `eplus/models/` copy when present, else
fall back to these pinned files under `vibe_code_apps_22/models/eplus/`.
