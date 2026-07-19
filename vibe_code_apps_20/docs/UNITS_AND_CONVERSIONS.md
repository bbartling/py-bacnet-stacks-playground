# Units and conversions

Canonical internal calculations are SI. Public inputs may be tagged IP or SI.

## Module

`wattlab.units` provides:

- `Quantity` with value, unit, and dimension
- Absolute temperature vs temperature-difference converters (never mixed)
- HVAC/energy/economic conversions (area, airflow, pressure, power, fuel, EUI, carbon, costs)
- Display helpers: Imperial / Metric / Source / Dual

## Rule

Do not infer units from field names alone. Prefer explicit unit tags in schemas and Studio display preferences. EnergyPlus IDF values remain SI regardless of display mode.

## Tests

```powershell
python -m pytest tests/test_units.py -q
```
