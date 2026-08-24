# AGENTS.md — Vibe 23 LBNL Building 59 calibration + DSM

**Mission:** turn the public LBNL Building 59 dataset into an auditable EnergyPlus existing-building model suitable for later DSM experiments.

**Current claim:** `CALIBRATION_BOOTSTRAP`. No calibrated-model, tariff-settlement or DSM-savings claim is authorized yet.

## Mandatory reading order
1. This file.
2. [`vibe23_agent_spec/SPEC.md`](vibe23_agent_spec/SPEC.md).
3. [`vibe23_agent_spec/DATA_CONTRACT.md`](vibe23_agent_spec/DATA_CONTRACT.md).
4. [`../agentic_ai/skills/energyplus-engineering/SKILL.md`](../agentic_ai/skills/energyplus-engineering/SKILL.md).
5. Then the routed shared skill for dataset, calibration, tariff or DSM work.

## Hard rules
- Never commit the 263 MB source archive or extracted multi-GB telemetry.
- Never guess point names; bind them from the real source metadata/inventory.
- Never call derived monthly meter totals `utility bills`.
- Never label a PG&E tariff as Building 59's actual tariff without evidence tying the rate to this building/account and period.
- Never tune aggregate kWh while ignoring peak kW, end-use shape, HVAC operation or zone temperatures when those measurements are available.
- Never call the model calibrated merely because EnergyPlus runs.
- Preserve model, weather, source-data, parameter-ledger and output hashes for published calibration runs.
- Change a small named parameter family per calibration iteration.
- DSM work is simulation-only until a calibrated/validated baseline and frozen experiment contract exist.

## Status ladder
`CALIBRATION_BOOTSTRAP` → `DATA_MAPPED` → `MODEL_SEED` → `CALIBRATION_IN_PROGRESS` → `MONTHLY_CALIBRATED` → `HOURLY_CALIBRATED` → optional `VALIDATED_HOLDOUT` → `DSM_RESEARCH_READY`.

## First milestone definition of done
- reproducible dataset download/extraction;
- real CSV/point inventory generated;
- whole-building meter and key end uses positively identified;
- evidence/assumption ledger updated;
- model seed topology based on sourced facts, not guesses;
- measured/simulated alignment pipeline in place;
- tests passing;
- no unsupported tariff or calibration claims.
