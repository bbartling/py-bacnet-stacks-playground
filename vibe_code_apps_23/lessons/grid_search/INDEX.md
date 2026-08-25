# Grid Search DSM Lessons — Index

Ten progressive lessons that teach **bounded grid search for demand-side management (DSM)** — first with pseudocode and fake data, then with stock EnergyPlus 26.1 ExampleFiles, ending with a PV + battery (BESS) bonus.

**Scaffold:** same as repo [`lessons/`](../../../lessons/) — `Goal` / `Concept` / `How to Use It` / `Why This Matters` / `Mini Examples` / `Micro Exercises` / `Key Takeaway`.

**Honesty banners (every day):**

- Educational only — stock ExampleFiles, not a calibrated school or Building 59 model
- Illustrative energy + demand dollars — not a complete utility bill
- **No BACnet** and no authority to write setpoints to a real BAS

**Prerequisites:** Python 3.10+, EnergyPlus 26.1 at `C:\EnergyPlusV26-1-0` (or set `ENERGYPLUS_ROOT`). Companion scripts live in [`scripts/`](./scripts/).

### Test whether EnergyPlus is installed locally

Run this **before Day 03** (Days 01–02 need no EnergyPlus):

```bash
cd vibe_code_apps_23/lessons/grid_search/scripts
python check_energyplus_install.py
```

Expect every line marked `[PASS]` and `RESULT: PASS`. Optionally, from `vibe_code_apps_23`:

```bash
vibe23 energyplus-doctor --out reports/runtime/energyplus_capability.json
```

| Day | Lesson | Companion |
| --- | --- | --- |
| 01 | [Grid-search pseudocode](./day01.md) | (markdown only) |
| 02 | [Fake-data grid search](./day02.md) | [`day02_fake_data_grid_search.py`](./scripts/day02_fake_data_grid_search.py) |
| — | Install check | [`check_energyplus_install.py`](./scripts/check_energyplus_install.py) |
| 03 | [First EnergyPlus run](./day03.md) | [`day03_first_eplus_run.py`](./scripts/day03_first_eplus_run.py) |
| 04 | [Tiny thermostat grid](./day04.md) | [`day04_tiny_thermostat_grid.py`](./scripts/day04_tiny_thermostat_grid.py) |
| 05 | [Expand the menu](./day05.md) | [`day05_expand_menu.py`](./scripts/day05_expand_menu.py) |
| 06 | [Demand limiting](./day06.md) | [`day06_demand_limiting.py`](./scripts/day06_demand_limiting.py) |
| 07 | [Night ventilation](./day07.md) | [`day07_night_ventilation.py`](./scripts/day07_night_ventilation.py) |
| 08 | [Small office reference](./day08.md) | [`day08_small_office.py`](./scripts/day08_small_office.py) |
| 09 | [Primary school readiness](./day09.md) | [`day09_primary_school.py`](./scripts/day09_primary_school.py) |
| 10 | [BESS / PV + battery bonus](./day10.md) | [`day10_bess_battery.py`](./scripts/day10_bess_battery.py) |

Shared helper: [`scripts/eplus_lab.py`](./scripts/eplus_lab.py).

See also: parent [Vibe 23 README](../../README.md).
