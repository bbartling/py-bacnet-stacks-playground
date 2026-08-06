# Lakeside Heating DSM — desktop walk (client package)

Windows app for a **96-step (15-min) hybrid** facility kW / zone-temp what-if:
`hybrid = real_baseline + eplus_delta`.

## Quick start

1. Unzip this folder (keep files together).
2. Double-click **`lakeside-heating-dsm.exe`**.
3. Open **Hybrid Real+E+ 96-step DSM** — baseline vs DSM trajectories.
4. Tariff panel is prefilled for **Creekside CP-2** (editable).

Required next to the `.exe`:

- `hybrid_dsm_96_v1_walk.json`
- `hybrid_ship_manifest.json`
- model cards / meta from `promote_hybrid_ship.py`

## Honesty

- Status: **`HYBRID_SCREENING`** — not tariff-grade until field DSM trials.
- Component A = measured BAS 15-min; component B = IdealLoads + fixed-COP deltas.
- Real BAS and EnergyPlus rows are **never** mixed in one train table.
- IdealLoads+COP ≠ GSHP plant.
- Quarantined `heating_dsm_hourly_v1.*` is **not** the ship model.

## Optional environment

| Variable | Purpose |
| --- | --- |
| `LAKESIDE_ONNX_DIR` | Folder with hybrid walk JSON / artifacts |
| `LAKESIDE_SITE_ROOT` | Site data root |
