# Lakeside Heating DSM — desktop walk (client package)

Windows app for a **96-step (15-min) hybrid** facility kW / zone-temp what-if:
`hybrid = real_baseline + eplus_delta`.

## Quick start

1. Unzip this folder (keep files together).
2. Double-click **`lakeside-heating-dsm.exe`**.
3. Set **midnight facility kW + 6 zone temps**, weather, strategy.
4. Click **Live hybrid: 24/7 vs DSM** — inference runs on local ONNX (not a static demo alone).
5. Tariff panel is prefilled for **Creekside CP-2** (editable).

Required next to the `.exe`:

- `real_baseline_15min_v1.onnx` + `_feature_meta.json`
- `eplus_delta_15min_v1.onnx` + `_feature_meta.json`
- `hybrid_dsm_96_v1_walk.json` (precomputed ship walk for compare)
- `hybrid_ship_manifest.json`

## Honesty

- Status: **`HYBRID_SCREENING`** — not tariff-grade / not operational DSM.
- Live Run = ONNX recursive 96-step from UI inputs; ship JSON is **compare/fallback**.
- IdealLoads+COP ≠ GSHP plant. Smoke E+ farm is underpowered.
- If `outcome_flag: DSM_WORSENS_PEAK`, the scenario is **not** a recommended strategy.
- Quarantined `heating_dsm_hourly_v1.*` is **not** the ship model.

## Optional environment

| Variable | Purpose |
| --- | --- |
| `LAKESIDE_ONNX_DIR` | Folder with hybrid ONNX / walk JSON |
| `LAKESIDE_SITE_ROOT` | Site data root |
| `VIBE22_ALLOW_SMOKE_PROMOTE` | Allow promote with &lt;12 E+ pairs (screening only) |
