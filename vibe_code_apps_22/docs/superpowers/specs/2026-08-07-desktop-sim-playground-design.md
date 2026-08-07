# Desktop sim playground notebook

**Date:** 2026-08-07  
**Status:** implemented

## Goal

A short fourth notebook that mirrors the Rust desktop Live Run using the same ONNX pair, without training or stamp spam.

## Notebooks

| Notebook | Role |
|---|---|
| `lakeside_desktop_sim_playground.ipynb` | Easy story: midnight → weather → ONNX walk → incremental $ → 24/7 overlay → strategy enumeration |
| `lakeside_load_profile_analysis.ipynb` | Meter/weather/GL14 analytics regen + shape gallery (separate panels) |
| sklearn / torch tutorials | Engine room; shouty honesty banners removed |

## Design choices

- ONNX via `hybrid_rollout.load_hybrid_onnx` (same artifacts as desktop).
- Incremental demand accounting from `simulation_contract`.
- Load-profile analytics call `demand_weather_charts.regenerate_analytics_charts` (no duplicate diurnal hand-plots).
- Overlay becomes a 3-panel shape gallery so mismatched days are obvious.
