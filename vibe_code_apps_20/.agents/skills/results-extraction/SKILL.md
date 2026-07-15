# Skill: results-extraction

Parse EnergyPlus tabular outputs into WattLab `result_record` annual fields.

## Source

Prefer `eplustbl.csv` via `results_parse.annual_from_output_dir`.

## Fields

- `electricity_kwh_year`
- `natural_gas_therm_year`
- `site_eui_kbtu_ft2_year`
- `utility_cost_usd_year` (from profile utility rates)

Always keep `input_hash` and artifact paths.
