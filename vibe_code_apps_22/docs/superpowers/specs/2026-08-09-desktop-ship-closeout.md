# 2026-08-09 — Desktop ship closeout (smoke)

Local four-arm bake-off → `ship_best_to_desktop` → desktop artifacts.

## Selection

| Field | Value |
| --- | --- |
| Selected arm | `sklearn_allyear` |
| Champion | `gradient_boosting` |
| Recursive peak MAE | **29.367 kW** |
| Zone MAE (mean) | ~1.27 °F |
| Winter runner-up | `sklearn_winter` / `extra_trees` @ 37.52 kW |
| Torch | not shipped (research only) |

Selection rule: lowest recursive held-out morning-peak MAE among sklearn arms; winter wins ties; torch never ships.

## Promote honesty

| Field | Value |
| --- | --- |
| `ship_mode` | `smoke_artifact` |
| Watermark | `UNDERPOWERED_SMOKE_FARM` |
| Usable both-arm pairs | **6** (&lt; 12 → smoke only) |
| `honesty` | `HYBRID_SCREENING` |
| `operational_dsm` | **false** |
| Multires hourly | fail (monthly utility GL14 pass separately) |

Command used:

```powershell
python -u scripts\ship_best_to_desktop.py --no-launch --allow-smoke-promote
```

## Validate

- `cargo test` (desktop): **32 passed**
- `pytest tests/test_ship_best_to_desktop.py tests/test_simulation_contract.py`: **6 passed**
- ONNX / walk / manifest written under `desktop/artifacts/` (gitignored; regenerate locally)

IdealLoads+COP deltas ≠ GSHP plant. Grow the paired E+ farm before claiming operational DSM.
