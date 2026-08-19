# Vibe22 physics/control-strategy comparison plots (2026-08-19)

Publication-quality GL14/calibration analytics from the **sp_creekside** practice pack,
copied into git for research-only diagnostic evidence.

No operational readiness, “implementation complete”, or BACnet authority claims.

## Manifests / provenance

- Plot inventory: [`figures/vibe22_final_physics_control_strategy_comparison/plot_manifest.json`](figures/vibe22_final_physics_control_strategy_comparison/plot_manifest.json)
- Source provenance: [`figures/vibe22_final_physics_control_strategy_comparison/plots/analytics/source_manifest.json`](figures/vibe22_final_physics_control_strategy_comparison/plots/analytics/source_manifest.json)

## Regenerate from site pack

```powershell
$env:SITE_ROOT = "C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
cd vibe_code_apps_22
python scripts/vibe22_publish_analytics_plots.py --build-enhanced-gl14 --overwrite
```

See also [`../../plots/w2a_dial/README.md`](../../plots/w2a_dial/README.md) for W2A enhanced-model GL14 gate charts.

## Sections

### IdealLoads GL14 calibration (`plots/analytics/`)

- `gl14_progress_by_iteration.png`, `gl14_status_by_iteration.png`
- Monthly kWh / fuel / peak panels vs utility bills
- `by_month/fuel_*_actual_vs_model.png`

### W2A dial — GL14 still holds after enhancement (`plots/analytics/eplus_gl14_vs_peak285/`)

Champion ladder **E20 → SC02 → R02 → A04** must pass utility monthly GL14 while pushing Jan-26 peak toward ~285 kW.

- `gl14_gate_scatter_enhanced.png` — NMBE vs CVRMSE gate box (PASS models labeled)
- `gl14_peak_pareto_enhanced.png` — peak vs CVRMSE dual objective
- `pareto_gl14_vs_peak.png`, `monthly_kwh_line_a04_ladder.png`, `peak_day_e20_sc02_r02_a04.png`
- Scorecards: `a04_dial_scorecard.csv`, `enhanced_gl14_payload.json`

### Site diagnostics (`plots/site_diagnostics/`)

- CS meter + geo loop + per-zone HP trend PNGs from site `plots/HP*.png`

## Honesty

- Partial-period **utility bill** GL14 screen — not purchased ASHRAE G14-2023
- Monthly GL14 pass ≠ interval-shape / 15-minute DSM GO
- W2A A04 parent passes GL14 but W2A low-airflow physics repair is separate work
