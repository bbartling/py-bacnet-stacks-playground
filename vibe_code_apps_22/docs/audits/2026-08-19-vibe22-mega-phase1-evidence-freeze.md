# Vibe22 mega Phase 1 evidence freeze (2026-08-19)

**Scope:** date-use ledger + completed research-long audit only. No new EnergyPlus runs. No policy development. Vibe19 untouched. BACnet commands = 0.

Machine-readable source of truth for Phase 2+: [`figures/vibe22_mega_phase1/phase1_evidence_freeze.json`](figures/vibe22_mega_phase1/phase1_evidence_freeze.json)

## Date-use ledger (frozen)

| Pool | Window / dates | Status |
| --- | --- | --- |
| RL training | 2025-11-01 → 2025-12-14 | frozen |
| Validation | 2025-12-15 → 2025-12-31 | frozen (selection only) |
| Adaptation development | *(empty)* | reserved for Phase 14 |
| Physics development | 2026-01-12, 2026-01-25, 2026-01-26, 2026-03-16 | development evidence |
| Locked test (nominal) | 2026-01-01 → 2026-01-31 | **`NO_PRISTINE_LOCKED_TEST_AVAILABLE`** |

January 2026 was already used for physics/P1 development. It must **not** be relabeled as an unseen holdout.

## Completed research-long audit (recomputed)

Run: `research_long_20260818T194337Z` on practice pack `sp_creekside`.

| Field | Value |
| --- | --- |
| Trained policies | 4 (PPO×2, DQN×2) |
| Valid transitions / seed | 8,192 each → **32,768 total** |
| Validation days | 17 |
| Evaluation rows | 187 |
| Readiness rate (all arms) | ~95.2% |
| `validation_selected_policy` | `trained_dqn_seed0` |
| Legacy `winner` key | same value preserved in audit |
| Locked unseen | **NO LOCKED UNSEEN TEST AVAILABLE** |
| A04 physics valid | **false** (W2A low-airflow remains) |

W2A low-airflow counts are parsed from every `eplusout.err` under the run root, with separate rollups per RL seed. See the JSON artifact for per-file totals.

## Regenerate (render-only)

```text
python scripts/vibe22_freeze_phase1_evidence.py ^
  --research-long-run %SITE_ROOT%\reports\eplus_gym\rl\research_long_20260818T194337Z
```

## Claim labels

`SIMULATION_ONLY_RL_RESEARCH` · `A04_RESEARCH_POC_NOT_TRANSIENT_VALIDATED` · `NO_BACNET_COMMAND_AUTHORITY` · not operational DSM.
