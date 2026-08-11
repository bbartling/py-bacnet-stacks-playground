# Lakeside Heating DSM — desktop (Rust)

Windows egui app for the **Hybrid Real+E+** 15-min × 96 DSM walk.

## Information architecture

- **Welcome** (default landing) — large centered intro; savings-claim status in M&V plain language.
- **Tutorial** — 10 guided steps with large centered copy (Welcome → Site → Fit screens → Tariff → Day → Baseline → Strategy → Nearest-Day → Day cost → **SIM**). Chrome: Back / Next / Skip to SIM / Exit to Workspace.
- **Workspace** — one folder at a time: Site & models · Tariff · Day & weather · Strategies · Validation · SIM Lab · Annual.

Thin top chrome: brand · mode switcher · one-line **Savings claim: …** · **Light/Dark** theme button. Fit screens speak NMBE / CV(RMSE) / n. Full multi-res detail under Workspace → Validation. Operator recommendation language stays fail-closed when screens fail.

IdealLoads + fixed-COP ≠ ground-source heat-pump plant.

## What it does

- **Fail-closed** without `hybrid_dsm_96_v1_walk.json` (baseline vs DSM trajectories).
- Honesty stamp: **`HYBRID_SCREENING`** (real BAS baseline + IdealLoads+COP deltas). IdealLoads+fixed-COP ≠ GSHP.
- Portable TOD + demand tariff (Creekside CP-2 defaults) for cost compare UI.
- Optional legacy hourly ONNX panel is **not** the ship path (quarantined).

Promote artifacts:

```powershell
python -u ..\scripts\ship_best_to_desktop.py --no-launch --allow-smoke-promote
cd vibe_code_apps_22\desktop
cargo test --release
cargo run --release
```

## Client package

```powershell
.\pack_client.ps1
```

See [`CLIENT_README.md`](CLIENT_README.md).
