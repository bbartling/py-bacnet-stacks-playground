# Building 59 CONTROL_REPLAY 30-run results

**Claim status:** `CONTROL_REPLAY_SCREENING_NOT_CALIBRATED`

Discrepancy-driven dial-in of SAT setpoint, zone setpoints, outdoor-air
minimum, and DX capacity/airflow on the existing screening topology. This does
**not** fix UFT / hydronic / water-plant blockers.

## Outcome

| Item | Value |
| --- | --- |
| Runs admitted | 30 / 30 |
| Monthly GL14 gate | **Not met** |
| Champion | `R14` (OA scale 1.10 × published minimum) |
| Champion full-year NMBE | −4.35% |
| Champion full-year CV(RMSE) | 22.40% |
| Baseline `R01` NMBE / CV(RMSE) | −4.13% / 22.36% |

Warming SAT toward measured BAS medians (~18.5–19.5 °C) required raising the
proxy zone cooling setpoint to keep `cool − SAT ≥ 5.5 °C` (otherwise
EnergyPlus emits fail-closed sizing warnings). Those SAT-led candidates did
**not** win the January–September monthly objective versus the cold 14.4 °C
SAT baseline on this PackagedVAV proxy.

## Learning retained in skills

See [`agentic_ai/skills/energyplus-calibration/SKILL.md`](../../agentic_ai/skills/energyplus-calibration/SKILL.md):
discrepancy-first axes, topology stop-rules, DX domain limits, and the
PackagedVAV 5 °C SAT-vs-zone sizing gate.

## Reproduce

```bash
cd vibe_code_apps_23
# weather/b59_2020_bounded_hybrid_amy.epw must exist (local; gitignored)
python scripts/run_b59_control_replay_30.py \
  --energyplus /path/to/energyplus \
  --epw weather/b59_2020_bounded_hybrid_amy.epw \
  --workers 3
```

Artifacts: this directory’s `campaign_log.csv`, `campaign_summary.json`,
`champion_parameters.json`, and `model/b59_control_replay_champion.generated.idf`.
