# ML artifacts (mostly **not** in git)

Trained models, farm parquets, figures, and ship JSON are **local / Google Drive**.
Git keeps only small **fixtures** (unit-test parity) and READMEs.

## What stays in the repo

| Path | Role |
| --- | --- |
| `fixtures/*.json` | Compact init/walk/nearest-day fixtures for pytest / Rust parity |
| `INTEGRITY_INVENTORY_*.md` | Historical integrity notes |
| `_quarantine_*/README.md` | Why old kW-only stems were retired |

## What you get from Drive (or regenerate)

| Stem / glob | Role |
| --- | --- |
| `real_baseline_15min_v1.{onnx,joblib,json}` | Sklearn real baseline (desktop ship) |
| `eplus_delta_15min_v1.{onnx,joblib,json,parquet}` | E+ delta arm |
| `real_baseline_15min_torch_v1.*` | Torch research alternate |
| `heating_dsm_eplus_paired_15min_v1.parquet` | Paired farm table |
| `figures/`, `eval/`, `runs/`, `hybrid_*walk*.json` | Regenerable train/ship outputs |

## Generate locally

```powershell
$env:LAKESIDE_SITE_ROOT="C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"
$env:VIBE22_ALLOW_CLI_TRAIN="1"
cd ..\..   # vibe_code_apps_22
python -u scripts\build_real_15min_store.py
python -u scripts\eplus_heating_dsm_farm.py --smoke
python -u scripts\train_four_arms.py --profile full_evaluation
$env:VIBE22_ALLOW_SMOKE_PROMOTE="1"
python -u scripts\ship_best_to_desktop.py --no-launch
```

Site weather / IDF / utility CSVs live under `LAKESIDE_SITE_ROOT` — see [`../../data/DATA.md`](../../data/DATA.md).
