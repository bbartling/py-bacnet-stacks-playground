# W2A dial GL14 gate charts

When a W2A plant model is **enhanced** (E20 → SC02 → R02 → A04 ladder), re-run the
GL14 chart builder before publishing to GitHub so each candidate still passes the
partial-period utility screen (|NMBE| < 5%, CVRMSE < 15%).

## Regenerate (site pack)

```powershell
$env:SITE_ROOT = "C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
python plots/w2a_dial/_build_enhanced_gl14_charts.py
```

Inputs (under ``SITE_ROOT/plots/analytics/eplus_gl14_vs_peak285/``):

- ``a04_dial_scorecard.csv`` — required; one row per champion ladder model
- ``enhanced_dial_trials.csv`` — optional; all dial attempts

Outputs (same directory):

- ``gl14_gate_scatter_enhanced.png`` — NMBE vs CVRMSE with gate box
- ``gl14_peak_pareto_enhanced.png`` — Jan-26 peak vs CVRMSE colored by pass/fail
- ``enhanced_dial_trials_gl14.png`` — trial peaks; blue = GL14 pass
- ``enhanced_gl14_payload.json`` — machine-readable summary

## Publish to GitHub

```powershell
python scripts/vibe22_publish_analytics_plots.py --build-enhanced-gl14 --overwrite
```

Copies curated PNGs + CSVs from ``SITE_ROOT/plots/`` into
``docs/audits/figures/vibe22_final_physics_control_strategy_comparison/`` and writes
``plot_manifest.json`` + ``source_manifest.json``.

**Honesty:** monthly utility GL14 ≠ 15-minute DSM GO. Passing GL14 does not mean
control-ready or operational DSM.
