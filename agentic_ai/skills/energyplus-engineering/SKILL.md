---
name: energyplus-engineering
description: Route shared EnergyPlus work to the right intake, authoring, calibration, tariff, results, or DSM procedure.
---

# EnergyPlus engineering router

## Goal
Provide one reusable engineering entry point for EnergyPlus work across the Vibe series.

## Route by task
- Public measured data intake → `../dataset-provenance/SKILL.md`
- Building profile, privacy, or source facts → `../building-intake/SKILL.md`
- Seed IDF, geometry, schedules, or HVAC representation → `../energyplus-model-authoring/SKILL.md`
- Existing-building calibration → `../energyplus-calibration/SKILL.md`
- Actual-year/typical weather → `../energyplus-weather/SKILL.md`
- EnergyPlus MCP operations → `../energyplus-mcp/SKILL.md`
- Output extraction and simulation QA → `../energyplus-results/SKILL.md`
- Rates, TOU, demand charges → `../utility-tariff/SKILL.md`
- Demand-side-management experiments → `../energyplus-demand-management/SKILL.md` (use `../dsm-experiment-design/SKILL.md` for the comparison contract)

## Core rules
1. Separate source facts, inferred parameters, assumptions, and optimization decisions.
2. Preserve model, weather, input-data and output hashes for published runs.
3. EnergyPlus autosizing is not proof of installed capacity.
4. A simulation completing successfully is not proof that the model is calibrated.
5. Use the simplest topology that still preserves the physical/control behavior required by the study.
6. Keep actual-year calibration weather distinct from TMY screening weather.
7. Change small, named parameter families per calibration iteration.
8. Never publish DSM savings without a calibrated/validated baseline, a frozen experiment contract, and an identical-condition candidate comparison.
9. Never present illustrative pricing as a utility bill.

## Companion GPT
The maintainer-supplied EnergyPlus Engineer Wizard GPT may be used interactively, but its live instructions are not version-pinned by this repo. Promote durable procedures into this skill tree before depending on them for reproducible work.

## Evidence statuses
`SOURCE_FACT` · `INFERRED_FROM_DATA` · `ENGINEERING_ASSUMPTION` · `MODEL_PARAMETER` · `CALIBRATED_PARAMETER` · `UNRESOLVED`
