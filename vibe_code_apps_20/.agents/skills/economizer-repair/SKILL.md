# Economizer Repair

## Purpose
Translate evidence of mechanical cooling when outdoor conditions permit free cooling into a defensible individual ECM.

## Invoke when
When evidence suggests mechanical cooling when outdoor conditions permit free cooling.

## Required inputs
- OAT, RAT/MAT/SAT, damper command/position, cooling status, sensor validity
- approved baseline
- implementation constraints

## Procedure
1. Validate sensors and prerequisites.
2. Confirm applicability and causal mechanism.
3. Quantify affected hours/loads without double counting.
4. Define exact baseline and proposed inputs.
5. Repair sensors, dampers, sequences, and lockouts before modeling improved economizer behavior.
6. Create MeasureBrief and verification plan.

## Outputs
- ECM brief
- EnergyPlus parameter map
- implementation and verification notes

## Guardrails
Do not report savings when prerequisites fail. Keep non-energy benefits separate from modeled energy.

## Validation
Evidence chain complete; parameter mapping reviewed; result passes QA.
