# ESCO spreadsheet calcs & ECM registry (human-readable)

Screening-grade formulas that WattLab Studio compares to EnergyPlus twin
results. Paybacks are **not** investment-grade — refine with site runtime,
rates, rebates, and remaining useful life.

**GitHub (develop tip):**
[ESCO_SPREADSHEET_CALCS.md](https://github.com/bbartling/py-bacnet-stacks-playground/blob/develop/vibe_code_apps_20/docs/ESCO_SPREADSHEET_CALCS.md)

Companion detail: [`../vibe20_agent_spec/docs/ESCO_CALCULATORS.md`](../vibe20_agent_spec/docs/ESCO_CALCULATORS.md)
· ROI cost bands: [`../vibe20_agent_spec/docs/ESCO_RETROFIT_COST_ROI.md`](../vibe20_agent_spec/docs/ESCO_RETROFIT_COST_ROI.md)

---

## Where the Python lives

| Layer | Path | Role |
| --- | --- | --- |
| Bin-method calculators | `wattlab/bench/esco.py` | Spreadsheet-analog HVAC bins (fan/sched/DAT/hydronic/ERV/…) |
| Simple algorithms | `wattlab/bench/algorithms.py` | Affinity laws, DCV OA, boiler η improvement, kW/ton, payback |
| Calculator registry | `wattlab/bench/registry.py` | `get(name)(inputs)` dispatch |
| Weather bins | `wattlab/weather/bins.py` | 5°F × 3-shift tables (`washington_dc_noaa`, AMY CSV) |
| Studio proxy wiring | `wattlab/studio/proxies.py` | Maps catalog ECM ids → calculator inputs from floor area |
| Per-ECM ROI costs | `wattlab/studio/ecm_roi.py` | `$/ft² × coverage_fraction` (engineer-editable) |
| Crosscheck E+ vs proxy | `wattlab/crosscheck.py` | Agreement ratio + verdict band |
| ECM catalog | `wattlab/measures/catalog.yaml` | Canonical ids, proxy name, EnergyPlus patch |
| Easy Button packages | `wattlab/ecm/packages.py` | incl. **`esco-top15`** |
| EnergyPlus patches | `wattlab/energyplus/patches/` | IDF mutators (`registry.py` dispatch) |
| Finance / capital plan | `wattlab/finance.py` | Payback, ROI, NPV rollup |

Golden anchors: `tests/test_esco_golden.py`.

---

## Top-15 ESCO HVAC ECMs → catalog

Bulk-select package **`esco-top15`** on Studio → ECMs → Easy Buttons.

| Rank | ESCO measure | Catalog id(s) | Proxy calculator | E+ patch |
| ---: | --- | --- | --- | --- |
| 1 | HVAC scheduling / opt start-stop | `ECM-AHU-SCHED-ALIGN` | scheduling_*_bins | `fan_avail_occupied_office` |
| 2 | RCx / controls optimization | `ECM-RCX-SETPOINT-REVIEW` | scheduling (screening) | — |
| 3 | Fan VFDs | `ECM-PREMIUM-FAN-VFD` | `fan_affinity` / static reset | `premium_fan_vfd` |
| 4 | Pump VFDs | `ECM-PUMP-VFD` | `pump_vfd` | — |
| 5 | Duct static-pressure reset | `ECM-DSP-RESET` | `static_pressure_reset` | — |
| 6 | Supply-air-temperature reset | `ECM-SAT-RESET` | `dat_reset_bins` | `sat_reset` |
| 7 | VAV minimum airflow | `ECM-VAV-MIN-RESET` | `static_pressure_reset` | — |
| 8 | Economizer repair | `ECM-ECON-REPAIR` | `dewpoint_economizer` | — |
| 9 | Demand-controlled ventilation | `ECM-DCV-CO2` | `dcv_bins` | — |
| 10 | Hot-water reset | `ECM-BOILER-RESET` | `hydronic_reset_bins` | — |
| 11 | CHW / CW plant optimization | `ECM-CHW-RESET`, `ECM-CW-RESET`, `ECM-CHILLER-LOCKOUT` | hydronic / economizer | lockout on chiller |
| 12 | Boiler combustion tune | `ECM-BOILER-TUNE` | `boiler_efficiency_improvement` | — |
| 13 | Advanced RTU controls | `ECM-ADVANCED-RTU` | bundled fan+econ+sched | — |
| 14 | HE / condensing boiler | `ECM-CONDENSING-BOILER` | `boiler_efficiency_improvement` | `condensing_boiler` |
| 15 | HE chiller replacement | `ECM-CHILLER-REPLACE-HIEFF` | `kw_per_ton_improvement` | `high_efficiency_chiller` |

Note: `ECM-BOILER-TUNE` and `ECM-CONDENSING-BOILER` are **incompatible** — Easy Buttons warns if both are checked.

---

## Human-readable formula snippets

### Fan / pump affinity
`Power ∝ speed³` → `savings_kwh = design_kw × hours × (n_base³ − n_prop³)`  
Code: `algorithms.fan_affinity`, `algorithms.pump_vfd`, `esco.static_pressure_reset`.

### Scheduling
Removed operating hours × fan kW + OA vent cooling/heating loads.  
Code: `esco.scheduling_fan_bins`, `scheduling_cooling_bins`, `scheduling_heating_bins`.

### Boiler efficiency (ECM-12 / ECM-14)
Delivered load MMBtu; input therms = `MMBtu × 10 / η`.  
Savings = therms(η_base) − therms(η_prop).  
Defaults in Studio: 80% → 84% (tune) or 95% (condensing).  
Code: `algorithms.boiler_efficiency_improvement`.

### ERV (sensible)
Recovered CFM = min(OA, exhaust) × ε; heating `1.08·CFM·ε·ΔT`, cooling enthalpy form.  
Code: `esco.erv_bins` (E+ IDF patch still stub — proxy-only for now).

---

## Per-ECM ROI (`$/ft²` × coverage)

Studio → ECMs → **Per-ECM ROI cost calculator**:

```text
implementation_cost = fixed_usd
                   OR floor_area_ft2 × coverage_fraction × usd_per_ft2
```

**Liberty example:** G36 on VAV AHUs needs ~50% of the building converted to full DDC:

| Field | Example |
| --- | ---: |
| Floor area | 140,000 ft² |
| `ECM-GL36-AIRSIDE` $/ft² | $6.00 |
| Coverage | **0.50** |
| Cost | 140k × 0.5 × $6 = **$420,000** |

Engineers edit `$/ft²`, coverage, or paste a **fixed_usd** quote. Prefills live in
`wattlab/studio/ecm_roi.py` (`DEFAULT_ECM_ROI_MODELS`).

---

## E+ vs spreadsheet crosscheck

When Twin report has `savings_by_measure` and proxies exist:

- **Δ kWh / Δ therms** = E+ − ESCO (and % of ESCO)
- **agreement_ratio** = E+ / ESCO (area-scaled when prototype ≠ site)
- **verdict** from `wattlab.crosscheck` (`IN_LINE`, `REASONABLE_METHOD_DIFFERENCE`, …)

Investigate when ratio is outside ~0.5–2× before publishing.

---

## Assumptions to challenge on every project

- Floor area and which fraction actually gets the measure
- Utility $/kWh and $/therm (demand charges often dominate)
- Existing vs proposed schedules / VFD hours
- Boiler / chiller baseline efficiency (nameplate ≠ seasonal)
- Prototype EnergyPlus geometry vs real plant (apply area_scale)
