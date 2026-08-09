# Campaign provenance reconstruction — `bounded_exec_20260807`

**Date:** 2026-08-08  
**Campaign:** `eplus/campaigns/bounded_exec_20260807/` (site SoT)  
**Issue:** An earlier `--rescore-existing` run overwrote `summary.json`, destroying the
immutable execution record.

## Recoverable (from trial dirs / ledger)

| Field | Source |
| --- | --- |
| Per-trial knobs, IDF/EPW hashes | `trials/*/trial_result.json` |
| EnergyPlus exit / severe / logs | `trials/*/sim/` + `energyplus` block in trial_result |
| Original trial statuses | Prefer first ledger.jsonl `event=trial` lines if present; else current trial_result `status` (may already be rescored) |
| Utility monthly pairs | `trials/*/utility_monthly_pairs.csv` (post-rescore) |

## Unrecoverable / uncertain

| Field | Notes |
| --- | --- |
| Original campaign `summary.json` as written at first `--run-eplus` | Overwritten; SHA of first execution summary unknown unless mirrored elsewhere |
| Exact original `written_utc` / aggregate n_failed at first write | Reconstruct approximate counts from trial statuses only |
| Pre-rescore `post_run_metrics` (scorecard-copied utility) | Intentionally replaced by trial-specific utility; do not restore that bug |

## Policy going forward

- Never overwrite `summary.json` on rescore.
- Write `summary_rescored_<UTC>.json` + `summary_rescored_latest.json` pointer.
- Link `original_summary_sha256` when the original file is still present.
- `B_equip_mult_mid` (equip_mult=1.0) is the **unchanged parent/baseline**, not an improved model.

Operational DSM remains **NO-GO**.
