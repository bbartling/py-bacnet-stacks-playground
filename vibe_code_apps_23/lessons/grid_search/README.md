# Vibe 23 — Grid Search DSM Lessons

Progressive tutorials that show the **same shape** as the Vibe22/Vibe23 DSM workflow:

`forecast → bounded candidate menu → simulate each plan → readiness gate → rank by cost`

…without claiming calibration, utility-bill completeness, or BACnet control authority.

## Quick start

```bash
cd vibe_code_apps_23/lessons/grid_search/scripts

# Day 02 — no EnergyPlus required
python day02_fake_data_grid_search.py

# Day 03 — first stock EnergyPlus run (needs EnergyPlus 26.1)
python day03_first_eplus_run.py

# Day 04 — tiny 2×2 thermostat grid on 5ZoneWaterLoopHeatPump
python day04_tiny_thermostat_grid.py

# Day 05 — full 16-run menu (or --quick for 4 corners)
python day05_expand_menu.py --quick
```

Set `ENERGYPLUS_ROOT` if EnergyPlus is not installed at `C:\EnergyPlusV26-1-0`.

## Lesson map

Open [`INDEX.md`](./INDEX.md).

## Origins

- Toy thermal demo: local `grid_search_dsm_demo.py` (stdlib six-zone model)
- Real E+ demo: local `energyplus_grid_search_demo.py` (WLHP + Chicago TMY3)

Those demos are ported/adapted here as Days 02 and 04–05.

## Outputs

Scripts write under `outputs/dayNN_*`. Generated run folders are local scratch; keep `outputs/.gitkeep`.
