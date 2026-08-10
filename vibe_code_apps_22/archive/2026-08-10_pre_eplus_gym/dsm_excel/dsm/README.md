# Lakeside heating DSM playground (vibe22)

Excel + CSV hooks for **6 BAS Area** occupancy / preheat schedules and a simple
**energy vs demand** cost compare.

Site historian / openfdd data stays under `VIBE22_LAKESIDE_ROOT` (`sp_lakeside`).

## Rebuild

```powershell
python -u scripts\build_dsm_excel.py
```

## Files

| Path | Role |
| --- | --- |
| `lakeside_zone_dsm_playground.xlsx` | Editable ZoneSchedule, Rates, Forecast24, Scenarios, CostCompare |
| `exports/zone_schedule_scenario.csv` | Default export (stagger_preheat) for notebooks |
| `exports/zone_schedule_*.csv` | One CSV per named strategy |

## Rebuild / export

```powershell
python -u scripts\build_dsm_excel.py
```

## Cost objective (PLACEHOLDER rates)

\[
\min \; c_e \sum_h \widehat{\mathrm{kW}}_h \cdot \Delta t \;+\; c_d \max_h \widehat{\mathrm{kW}}_h
\]

Comfort / “warm by 07:00” is deferred to EnergyPlus sims. Rates sheet defaults
are **not** a utility tariff.

## Workflow

1. Edit `ZoneSchedule` occ_frac columns (0–1) or pick a strategy template CSV.
2. Paste next-day OAT into `Forecast24` (or replay AMY / Open-Meteo).
3. Run sklearn or ONNX model (`notebooks/…`) to fill `CostCompare`.
4. Later: swap training rows for an E+ DM farm; keep `FEATURE_COLS` stable.
