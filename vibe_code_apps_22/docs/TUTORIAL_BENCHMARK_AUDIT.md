# Tutorial Benchmark Audit — Multi-output DSM Notebooks

**Branch:** `feat/vibe22-multioutput-tutorial-notebooks`  
**Date (UTC):** 2026-08-06  
**Product claim:** `HYBRID_SCREENING` only — not operational DSM.

## What changed

1. **Root-cause fix (PyTorch ~24°F zone MAE)**  
   Prior trainer used feature-only `StandardScaler`, unweighted `MSELoss` on raw kW+°F, a single `Linear→7` head, and early-stop on facility_kw MAE only.  
   New trainer (`ml/train_real_baseline_torch_15min.py`):
   - Per-target `MultiTargetScaler` (`ml/target_scaling.py`) fit on **train days only**
   - Dual heads (facility_kw + 6 zones)
   - Huber loss in **normalized** space with `w_kw` / `w_zone`
   - Early-stop on all-target normalized MAE
   - Curriculum short-horizon pressure + recursive-96 selection on shared chrono folds
   - ResMLP dual-head (+ GRU candidate in full mode); lean path uses 1 seed

2. **Shared modules:** `metrics_report.py`, `run_provenance.py`, expanded `notebook_plots.py`

3. **CLI reproduction:** `scripts/run_sklearn_tutorial_train.py`, `scripts/run_torch_tutorial_train.py`

4. **Notebooks rebuilt** as tutorial benchmarks (sections 1–17, metric-driven honesty cell)

5. **Sklearn/delta cards** stamp `run_id` + artifact hashes

## Models compared

| Family | Role |
|---|---|
| Persistence / ridge (sklearn path) | Naive / linear baselines |
| Random Forest, ExtraTrees, Gradient Boosting | Sklearn bake-off (desktop ship path) |
| ResMLP dual-head | Fixed torch candidate |
| GRU dual-head | Optional torch temporal candidate (full mode) |

## Did the scaling defect fix work?

**Yes.** Lean torch retrain (`--lean --max-days 24`):

| Metric | Before (broken) | After (fixed) |
|---|---|---|
| TF `zone_temp_mae_mean` | ~24.3 °F | **~0.70 °F** |
| TF worst-zone MAE | (hidden in mean) | **~1.14 °F** |
| Recursive zone mean (held-out folds) | `not_evaluated` / poor | **~1.82 °F** (3 days) |

Facility kW TF MAE remains non-trivial (~24 kW on lean folds); recursive/locked facility errors are still large — torch is **not** a desktop champion.

## Did deep learning beat the sklearn champion?

**No — not for operational / recursive facility demand.**  
Sklearn ExtraTrees remains the ship baseline path. Torch improved *zone* TF dramatically after the scaler/loss fix but does **not** outperform ExtraTrees on recursive facility peak / locked winter test in this lean run. Deep models are research candidates only.

## Promotion / desktop champion

- Torch **never** overwrites desktop artifacts.
- Sklearn promote remains fail-closed: 6-pair farm → smoke watermark `UNDERPOWERED_SMOKE_FARM` only when `VIBE22_ALLOW_SMOKE_PROMOTE=1`.
- Operational promotion did **not** occur.

## Verification commands

```powershell
cd vibe_code_apps_22
python -m pytest tests -q --tb=short

$env:VIBE22_ALLOW_CLI_TRAIN="1"
$env:LAKESIDE_SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
python scripts/run_torch_tutorial_train.py --lean --winter-only --max-days 24 --epochs 25
# optional full sklearn A+B:
# python scripts/run_sklearn_tutorial_train.py --winter-only --max-days 36
```

## Remaining blockers (unchanged)

- Larger designed EnergyPlus strategy farm (≥12 both-arm pairs)
- Interval-calibrated GSHP / electrical plant (IdealLoads+COP ≠ plant)
- Field DSM trials
- Calibrated uncertainty / OOD / safety process
- Torch locked-test facility errors still far from operational quality

**Status:** RESEARCH/TUTORIAL ONLY.
