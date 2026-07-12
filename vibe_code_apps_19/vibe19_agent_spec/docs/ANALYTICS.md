# Analytics (Overview + DOCX pack)

**Audience:** agents / engineers reviewing Overview, analytics.docx, and operational filters.

## Where analytics live

| Surface | Content |
| --- | --- |
| **Overview** | Dataset span, occupancy calendar, plant motor weekly, mech-cooling OAT bins, **BAS vs web OAT histogram** |
| **Metering** (main section) | Monthly electric/gas vs CDD/HDD (starts the Metering category; RCx still has metering presets at the end) |
| **analytics.docx** (DOCX pack) | Motor weekly, cool bins, RCx coverage, **fan All/on/off** and **pump All/on/off** leave-temp summary tables |
| **RCx Plots** | Fan-mode summary stats on air-side presets; zone comfort ranking |

There is **no** duplicate Analytics main tab (removed intentionally). Overview owns building rollups.

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

## DOCX pack

After **Run Rules**, **Download DOCX pack (ZIP)** includes `analytics.docx` with the gated summary tables and a **Key findings** placeholder at the top.
