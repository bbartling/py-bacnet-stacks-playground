# WattLab data contract

Every artifact an agent reads or writes, with shapes. Breaking any of these
requires updating the tests named next to each section.

## 1. vibe19 WattLab dump (input seed)

Produced by vibe19 Export → **Build WattLab dump (zip)**. Loaded by
`wattlab.seed.load_bundle(path)` (zip or extracted folder; single wrapping
folder tolerated). Tests: `tests/test_seed_bundle.py`.

| File | Contents |
| --- | --- |
| `MANIFEST.json` | Index of every file (`path`, `kind`, `columns`, `purpose`, `how_to_use`) — agent reads this first |
| `model_seed.json` | Data-derived seed: data_window, schedule_hints; building_type / floor_area / bills tagged `user_required` when absent |
| `schedule_inference.json` / `schedule_inference_table.csv` | Inferred occupied schedules per equip |
| `operating_signatures.csv` | OAT-bin operating signatures (the "Weather Man" equivalent) |
| `sensor_stats_all.csv` / `sensor_stats_fan_on.csv` / `sensor_stats_fan_off.csv` | Per-role summary stats sliced by fan proof |
| `sensor_diurnal_24h.csv` | Critical sensors × hour × `day_type` (weekday/weekend/holiday) × `fan_state` (all/on/off) |
| `setpoints.csv` | Occupied/unoccupied medians of `*-sp` roles |
| `mech_cooling_oat_bins.csv` + `mech_cooling_coverage.csv` | Mechanical-cooling hours by OAT bin (aggregated + per device) + inclusion/exclusion report |
| `motor_hours.csv` / `motor_weekly.csv` | Motor runtime rollups |
| `fdd_summary.csv` | Fault rollup (rule id, device, fault hours/pct) |
| `fdd_findings.csv` | Long-format findings with flattened metrics + `confirmed_fault` |
| `fdd_timeseries/<rule>__<equip>.csv` | Per-rule fault masks (`raw_fault`, `confirmed_fault`) + plot series |
| `topology.csv` / `data_model.csv` | Equipment feeds/fedBy + point bindings |
| `sensor_health_matrix.csv` / `sensor_fault_summary.csv` | SV-* health |
| `rcx_preset_coverage.csv` / `rcx_zone_comfort_ranking.csv` | RCx coverage + zone comfort ranking |
| `meter_monthly_electric.csv` / `meter_monthly_gas.csv` | Monthly meters when mapped |
| `weather_observed.csv` | Hourly observed weather → AMY EPW |
| `utility_bills.csv` | Monthly kWh / therms when the human entered them |
| `README_WATTLAB.md` | Human-readable dump guide |

`gap_report(bundle)` → rows `{field, severity, why, status, value}`. Severity
`required`: building_type, city, floor_area_ft2. The human always owes:
geometry confirmation, bills, rates, measure costs.

## 2. campus.json (utility-meter relationships)

Loaded by `wattlab.benchmarks.Campus.from_json`. Canonical example:
[`../examples/liberty/campus.json`](../examples/liberty/campus.json).
Tests: `tests/test_benchmarks_liberty.py`.

```json
{
  "campus_id": "liberty",
  "buildings": [
    {"building_id": "liberty_50", "floor_area_ft2": 140000, "property_type": "office"}
  ],
  "meters": [
    {"meter_id": "elec_shared", "fuel": "electricity", "unit": "kwh",
     "file": "Liberty_50_100_Electric_Summary.csv",
     "serves": ["liberty_50", "liberty_100"],
     "allocation": {"method": "area_weighted"}}
  ]
}
```

- `serves` length > 1 ⇒ shared meter ⇒ allocation is a **scenario** (`area_weighted` / `equal` / `gas_share` / `manual`).
- Bill CSVs: month column + usage column (kWh or Mcf) autodetected; thousands
  separators OK; duplicate bill months summed; demand kW → month max.
- `annual_summary` picks the **latest common complete 12-month window** across
  all meters unless given one.

## 3. Building profile (resolve_profile output)

`wattlab.defaults.resolve_profile(minimal)` → full profile with
`field_sources` provenance per field (`user` / `archetype` / `climate` /
`code`). Key fields: `conditioned_floor_area_ft2` (canonical area key — not
`floor_area_ft2`), `building_type`, `city`, `hvac`, `utility`
(`elec_usd_per_kwh`, `gas_usd_per_therm`). Optional: `proxy_savings`
(`{measure_id: {savings_kwh, savings_therms}}`) — presence triggers the
crosscheck block in easy-button reports.

## 4. Easy-button report (`wattlab_report.json`)

`run_easy_button(profile, ...)` → `run_id`, `steps`, `approved_measure_ids`,
`annual` + `monthly` results, `savings_by_measure`
(`[{measure_id, vs_baseline: {...}, vs_previous: {kwh_saved, therms_saved}}]`),
and `crosscheck` (below) when proxies exist. Dry-run: `{dry_run: true, steps,
approved_measure_ids}`. Tests: `tests/test_wattlab_easy_button.py`.

## 5. Crosscheck block

`wattlab.crosscheck.crosscheck_report` →

```json
{
  "overall_verdict": "in_line | investigate | keep_iterating",
  "measures": [{"measure_id": "...", "ep_savings_kwh": 0, "proxy_savings_kwh": 0,
                 "ratio": 1.2, "verdict": "in_line", "hint": "..."}],
  "g14": {"nmbe_pct": 0, "cvrmse_pct": 0, "nmbe_pass": true, "cvrmse_pass": true}
}
```

Bands: ratio 0.5–2.0 `in_line`; outside `investigate`; sign flip / zero proxy
vs big E+ `keep_iterating`. G14: monthly NMBE ±5%, CV(RMSE) ≤15%.
Tests: `tests/test_finance_crosscheck.py`.

## 6. Capital plan (`wattlab.finance.capital_plan`)

`{measures: [...], totals: {...}}` — per measure: `implementation_cost_usd`,
`kwh_saved`, `therms_saved`, `annual_cost_saved_usd`, `simple_payback_years`,
`roi_pct`, `npv_usd`, `assumptions`. Sorted by payback ascending (None last).
Export via `plan_to_csv` / `plan_to_json`.

## 7. Guardrail gate (`gate_capital_plan`)

Input: capital plan + `property_type`, `floor_area_ft2`, optional
`baseline_kwh/therms`, `site_eui_kbtu_ft2`, `glazing_area_ft2`. Output:

```json
{"verdict": "PUBLISH | INVESTIGATE", "investigate_count": 0,
 "checks": [{"check": "baseline_eui_band | savings_fraction | post_retrofit_eui |
              measure_cost_band | payback_plausibility",
             "status": "ok | investigate | skipped", "detail": "..."}]}
```

Missing context → `skipped`, never a false block.
Tests: `tests/test_benchmarks_guardrails.py`.

## 8. Benchmark registries (data files)

- `wattlab/data/benchmarks/benchmarks_public.json` — rows
  `{benchmark_name, property_type, p50, p20, p80, source, source_date, confidence}`;
  site EUI kBtu/ft²-yr. Fallback row `property_type: "commercial_all"` (CBECS 70.6) is mandatory.
- `wattlab/data/benchmarks/retrofit_costs_public.json` — rows
  `{scope, unit_basis, lo, p50, hi, currency_year, source, confidence}`.
  Scopes: `rcx_tuning`, `minor_hvac_controls`, `bas_overlay`, `major_hvac`,
  `non_energy_capital`, `windows_full_replacement`, `windows_secondary`, `deep_retrofit`.

## 9. Units and conversions (everywhere)

| Quantity | Unit | Conversion |
| --- | --- | --- |
| Site EUI | kBtu/ft²-year | — |
| Electricity | kWh | 1 kWh = 3,412 Btu |
| Gas (bills) | Mcf | 1 Mcf = 1.037 MMBtu = 10.37 therms |
| Gas (savings) | therms | 1 therm = 100 kBtu |
| Enthalpy | Btu/lb dry air | Hyland-Wexler saturation (see `weather/bins.py`) |
| OAT bins | 5°F wide × 3 daily shifts (12am-8am / 8am-4pm / 4pm-12am) | — |
