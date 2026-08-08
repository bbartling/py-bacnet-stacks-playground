# PR #76 actionable findings — status (2026-08-07)

Addressed in this calibration / honesty pass (verify against current code):

| Finding | Status |
| --- | --- |
| Interval monthly mislabeled as utility / GL14 | Fixed: separate `monthly_utility` vs `monthly_interval`; partial-period labels; desktop badges split |
| `--run-eplus` no-op | Fixed: real EnergyPlus trial loop with status machine |
| Holdout policy without enforcement | Chronological periods + locked 30-day holdout recorded; tuning must use calib/val only |
| Design-day duplicate stamps | `dedupe_eplus_stamps_keep_last` before scoring |
| Shape mismatch silent truncate | `ShapeMismatchError` in metrics engine |
| Mixed-unit `horizon_mae_curve` | Facility kW only for scalar keys; zone mean separate |
| Empty LOO → OOD fail-open | Already fail-closed (`threshold=0`) |
| Every fold invalid still exports champion | Raises `ValueError` |
| `require_complete=False` dead | Pads incomplete days when False |
| E+ delta no compatibility cap | `EPLUS_DELTA_MAX_COMPAT_DISTANCE` |
| `run_sklearn_tutorial_train` syntax | Already fixed prior |

Remaining / deferred (documented, not blocking this NO-GO calibration result):

- Some nearest-day / notebook plot-loop and generator `_reindent_py` items from CodeRabbit — track separately if still open.
- Full zone-temperature measured-vs-modeled gallery requires BAS zone series alignment not present in the E+ meter CSV alone.
