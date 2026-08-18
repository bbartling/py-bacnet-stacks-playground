# Analytics (Overview + Export analytics.docx)

**Audience:** agents / engineers reviewing Overview, Export analytics.docx, and operational filters.

## Where analytics live

| Surface | Content |
| --- | --- |
| **Overview** | Dataset span, occupancy calendar, plant motor weekly, mech-cooling OAT bins + **always-visible device coverage**, **BAS vs web OAT histogram** |
| **Metering** (main section) | Monthly electric/gas vs CDD/HDD (starts the Metering category; RCx still has metering presets at the end) |
| **Export → analytics.docx** | Motor weekly, cool bins, RCx coverage, **fan All/on/off** and **pump All/on/off** leave-temp summary tables |
| **Export → WattLab dump** | `wattlab_dump_v3` profiles (`summary` default / `diagnostic` / `forensic`): complete cookbook FDD + analytic CSVs (`mech_cooling_oat_bins.csv` with `series_kind`, `mech_cooling_coverage.csv`), shared `telemetry/`, expanded sensor stats + provenance; always re-runs all rules before zip |
| **RCx Plots** | Fan-mode summary stats on air-side presets; zone comfort ranking |
| **Plots → FDD DOCX** | **Not** analytics — dumb template of description + equation + plot stub only |

There is **no** duplicate Analytics main tab (removed intentionally). Overview owns building rollups. There is **no** Run Rules DOCX ZIP pack.

## Mechanical-cooling proof modes (compressor only)

**Override (2026-07-19):** CHW **pump status/command alone no longer proves compressor operation**. Weekly motor charts may still use designated pumps; OAT-bin / coverage runtime requires compressor-device evidence.

Eligible equipment: chillers/CHW plants, explicitly DX AHU/RTU, cooling-mode heat pumps, VRF outdoor units, typed compressor equipment. **Excluded:** chilled-water AHU valves (`clg_valve_pct` / cooling valve %), cooling demand alone, fan/pump status alone, temperature response alone.

Acceptable proof (deterministic priority): compressor/chiller **status** → verified **command** → analog **power/current** (unit-aware thresholds). Stage statuses OR for unit-active hours. Heat-pump compressor status counts only when cooling mode is proven.

Sidebar checkbox **Use mapped mechanical-cooling status proof** (`use_mech_cooling_status_proof`, default **checked**):

| Mode | Behavior |
| --- | --- |
| Checked (default) | CHW plant / DX: status → verified cmd → amps/power. **Not** `chw_pump_*`. |
| Unchecked | CHW plants only: CHW leaving / supply temp below **CHW leave proof max °F**. Proof labeled `inferred: chw_leave_temp`. Never applied to chilled-water AHU valves. Slider **disabled** while status proof is checked. |

Coverage always lists every cooling-capable device with:

- `eligibility_state` / `activity_state` / `proof_quality` / `proof_role`
- Runtime hours and valid elapsed / coverage %
- Exclusion reason when not compressor-based or missing proof

A mapped compressor that stays off is **`eligible_no_runtime`** (included), not excluded. Temperature-derived runtime is clearly labeled **inferred**.

### Device-hours vs any-active

OAT-bin rows publish explicit `series_kind`:

| `series_kind` | Meaning |
| --- | --- |
| `individual_device` | Per eligible compressor |
| `aggregate_device_hours` | Sum of every eligible device's runtime (`equipment_id="ALL"` compatibility) |
| `aggregate_active_hours` | Elapsed duration where **at least one** eligible compressor is running (union) |

Invariants: active-hours ≤ device-hours ≤ sum of individuals; active-hours ≤ valid elapsed. When **only one** device ran in a bin, any-active equals that device's hours (UI explains the equality).

APIs: `mech_cooling_run_mask`, `mech_cooling_coverage`, `mech_cooling_oat_bins` (`use_status_proof=`). Plot: `mech_cooling_oat_histogram` renders **individual devices as stacked bars**; **aggregate device-hours** and **any-compressor-active** are separate **non-stacked** marker lines (not additional bars).

## Operational filtering (the point)

Engineers need summary statistics **while the system is energized**:

| Slice | Proof | Used for |
| --- | --- | --- |
| Fan All / on / off | `fan_status` → `fan_cmd` → `zone_flow` | Air-side leave / SAT cohort stats (`fan_mode_summary_bundle`) |
| Pump All / on / off | `resolve_hydronic_running` (`chw_pump_status`, pump cmds, flow) | Plant leave-temp (`chw_supply_t` / `hw_supply_t`) via `pump_mode_summary_bundle` |

Rules still use `RULE_GATES` independently (`OPERATIONAL_GATES.md`). Analytics / RCx summaries must not silently drop pump-on slices when pump proof exists.

APIs:

- `app.analytics.plant_gated_summary_tables`
- `app.rcx_plots.fan_mode_summary_bundle`
- `app.rcx_plots.pump_mode_summary_bundle`

## Weather BAS vs web

- Overview histogram: `app.charts.bas_vs_web_oat_histogram` (BAS − web °F).
- Cookbook rule `OAT-METEO` still flags sustained disagreement.
- Mech-cooling OAT bins prefer **web** OAT by default.

## Export analytics.docx

**Export** can download `analytics.docx` with gated summary tables and a **Key findings** placeholder. The Plots **FDD DOCX** is a separate dumb equation template and does not include analytics.

## WattLab dump completeness + v3 migration

`Build WattLab dump (zip)` **always** executes `run_rules` for the complete active cookbook immediately before packaging. It does **not** reuse potentially partial session `batch_results`. The fresh complete result set replaces session `batch_results` and is what lands in `fdd_findings.csv` / evidence.

| Topic | Contract |
| --- | --- |
| Schema | `wattlab_dump_v3` (additive; Vibe 20 still loads v2) |
| Default profile | **`summary`** — no Cartesian per-rule `fdd_timeseries`; shared `telemetry/<equip>.csv` indexed by consumers |
| Other profiles | `diagnostic` / `forensic` add more rule evidence; skip statuses never emit timeseries |
| Mechanical tables | Preserve `series_kind` / coverage columns; do not require legacy fdd evidence layout |
| Sensor stats | Expanded percentiles, missingness, duration_hours, fan/occ slices; `inferred_parameters` carry provenance/confidence |
| Manifest metrics | Profile, result-status counts, files written/suppressed, payload bytes, `stage_seconds` |

Vibe 20 `wattlab.seed.load_bundle` accepts v2 + v3, exposes `schema_version` / `export_profile`, and indexes telemetry paths lazily without requiring `fdd_timeseries/`.
