# Analytics (Overview + Export analytics.docx)

**Audience:** agents / engineers reviewing Overview, Export analytics.docx, and operational filters.

## Where analytics live

| Surface | Content |
| --- | --- |
| **Overview** | Dataset span, occupancy calendar, plant motor weekly, mech-cooling OAT bins + **always-visible device coverage**, **BAS vs web OAT histogram** |
| **Metering** (main section) | Monthly electric/gas vs CDD/HDD (starts the Metering category; RCx still has metering presets at the end) |
| **Export → analytics.docx** | Motor weekly, cool bins, RCx coverage, **fan All/on/off** and **pump All/on/off** leave-temp summary tables |
| **Export → WattLab dump** | Complete cookbook FDD + analytic CSVs (`mech_cooling_oat_bins.csv`, `mech_cooling_coverage.csv`, …); always re-runs all rules before zip |
| **RCx Plots** | Fan-mode summary stats on air-side presets; zone comfort ranking |
| **Plots → FDD DOCX** | **Not** analytics — dumb template of description + equation + plot stub only |

There is **no** duplicate Analytics main tab (removed intentionally). Overview owns building rollups. There is **no** Run Rules DOCX ZIP pack.

## Mechanical-cooling proof modes

Sidebar checkbox **Use mapped mechanical-cooling status proof** (`use_mech_cooling_status_proof`, default **checked**):

| Mode | Behavior |
| --- | --- |
| Checked (default) | CHW plant: `chw_pump_*` → `chiller_status` → amps → power. DX devices keep compressor proof. |
| Unchecked | CHW plants only: CHW leaving / supply temp below **CHW leave proof max °F**. Proof labeled `inferred: chw_leave_temp`. The leave-temp slider is **disabled** while status proof is checked. |

Always show every cooling-capable device in Overview coverage with:

- Device name
- Included / excluded state
- Selected proof
- Inferred runtime hours
- Exclusion / warning reason

Temperature-derived runtime is clearly labeled **inferred** (cold water can flow through an idle chiller). Aggregate OAT-bin bars remain **device-hours** (`ALL` = sum across devices). Never use AHU CHW valve % as compressor proof.

APIs: `mech_cooling_run_mask`, `mech_cooling_coverage`, `mech_cooling_oat_bins` (`use_status_proof=`).

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

## WattLab dump completeness

`Build WattLab dump (zip)` **always** executes `run_rules` for the complete active cookbook immediately before packaging. It does **not** reuse potentially partial session `batch_results`. The fresh complete result set replaces session `batch_results` and is what lands in `fdd_findings.csv` / timeseries.
