# Ship best sklearn arm → desktop sim

Date: 2026-08-07  
Status: approved (approach A)

## Goal

After `train_four_arms`, auto-select the best **sklearn** arm, promote hybrid artifacts into `desktop/artifacts/`, and launch the desktop sim.

## Flow

1. Read `ml/artifacts/runs/sklearn_winter` and `sklearn_allyear` (`result.json` + model card).
2. Score = recursive peak MAE (`facility_kw_mae_peak_05_09`); lower wins; winter wins ties.
3. Copy winner’s `real_baseline_15min_v1*` into `ml/artifacts/` (keep existing `eplus_delta_15min_v1*`).
4. Call `promote_hybrid` → `desktop/artifacts/`.
5. `cargo run --release` from `desktop/` (unless `--no-launch`).

## Entry points

- `python scripts/ship_best_to_desktop.py`
- `python scripts/train_four_arms.py ... --ship-desktop` (runs ship after arms OK)

## Non-goals

- Torch never ships to desktop.
- Does not retrain delta.
- On promote gate failure: stop; do not launch.
