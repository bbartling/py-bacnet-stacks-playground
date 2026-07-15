# Baseline Model

## Purpose
Create and freeze a defensible Sketchbox baseline.

## Invoke when
Before any ECM runs or when baseline inputs change.

## Required inputs
- Approved BuildingProfile
- shell/HVAC/schedule mappings
- code baseline
- baseline checklist

## Procedure
1. Create/load project.
2. Populate Project, Design, Schedules, and Baseline tabs.
3. Track blue responsive defaults and overrides.
4. Read back critical values.
5. Save/export.
6. Run baseline.
7. Hash inputs and outputs.

## Outputs
- baseline manifest
- screenshots
- project export
- baseline results

## Guardrails
Do not alter baseline solely to increase measure savings. Any recalibration invalidates descendant measure comparisons.

## Validation
Model-readiness and results-QA checklists pass.
