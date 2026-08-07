# 2026-08-07 — Notebook polish + G14 ship precision + desktop wiring

## Goal

Make the three Lakeside notebooks look like short reports (theme + metric cards),
run them on a **smoke** farm, promote the bake-off champions into desktop artifacts,
and make the Rust app show **programmatic** champion names plus ASHRAE G14-style
**NMBE / CV(RMSE)** (MAE secondary) with a screening ± band — no hardcoded zeros.

## Decisions (approved)

| Topic | Choice |
|---|---|
| Visual polish | Report-style: theme + cards + tighter prose |
| Precision story | G14 posture: NMBE / CV(RMSE) primary; MAE secondary |
| Train depth | Smoke farm (`VIBE22_ALLOW_SMOKE_PROMOTE=1`) |
| Ship architecture | Artifact-driven fixed stems; UI reads promote outputs |

## Design

### 1. Notebooks (visual)

- Shared `apply_notebook_theme()` in `ml/notebook_plots.py` (colors, spines, dpi).
- Markdown metric cards (HTML) for G14 + MAE headlines after train/promote.
- Generators (`_gen_tutorial_notebooks.py`, `_gen_load_profile_analysis_nb.py`)
  regenerate all three notebooks; ASCII-safe prose; less print spam.

### 2. Held-out metrics → promote → ship

Train A/B already emit recursive held-out MAE/RMSE. Extend champion headlines with:

- `facility_kw_cv_rmse` (fraction, e.g. 0.18)
- `facility_kw_nmbe` (fraction, signed)
- Keep MAE/RMSE/peak MAE; zone mean MAE secondary for comfort.

`promote_hybrid_ship.py` writes these into walk JSON + `hybrid_ship_manifest.json`
under existing `baseline_cv_recursive_96_heldout` / `delta_*`, plus a display block:

```json
"mv_precision": {
  "primary": ["nmbe", "cv_rmse"],
  "secondary": ["mae", "rmse", "mae_peak_05_09"],
  "precision_pm_kw": <baseline peak MAE>,
  "g14_monthly_reference": {
    "nmbe_abs_max": 0.05,
    "cv_rmse_max": 0.15,
    "note": "ASHRAE G14 monthly calibrated reference; hybrid interval metrics are screening only"
  },
  "champion_baseline": "...",
  "champion_delta": "..."
}
```

Also stamp `precision_pm_kw` onto each arm's `_feature_meta.json` at promote time
so ONNX meta stays consistent with the ship.

### 3. Rust desktop

- Load `hybrid_ship_manifest.json` beside ONNX (same resolve order as walk).
- Prefer manifest champions / honesty / watermark for banner + hybrid panel.
- Set `precision_pm` from `mv_precision.precision_pm_kw` (fallback: held-out peak MAE).
- Metrics panel: NMBE (%), CV(RMSE) (%), MAE ±, G14 reference note, smoke watermark.
- Never hardcode `precision_pm = 0.0` when manifest/held-out metrics exist.
- Label ± as **screening precision**, not a statistical CI / operational G14 pass.

### 4. Run order (this pass)

1. Regenerate notebooks from generators.
2. Run load-profile → sklearn (train + smoke promote) → torch (no ship overwrite).
3. `cargo run --release` with `LAKESIDE_SITE_ROOT` set.

Honesty remains `HYBRID_SCREENING`; smoke → `UNDERPOWERED_SMOKE_FARM` /
`ship_mode=smoke_artifact`. IdealLoads≠GSHP disclaimer unchanged.

## Out of scope

- Versioned multi-ship registry / in-app model picker.
- Torch overwrite of desktop ship stems.
- Bootstrap confidence intervals.
- Claiming operational DSM / monthly G14 compliance from smoke interval metrics.
