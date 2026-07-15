# Schedule Optimization

## Purpose
Translate evidence of fan/plant operation outside required hours into a defensible individual ECM.

## Invoke when
When evidence suggests fan/plant operation outside required hours.

## Required inputs
- occupied and unoccupied schedules, fan status, exceptions
- approved baseline
- implementation constraints

## Procedure
1. Validate sensors and prerequisites.
2. Confirm applicability and causal mechanism.
3. Quantify affected hours/loads without double counting.
4. Define exact baseline and proposed inputs.
5. Reduce avoidable runtime while preserving warm-up, critical loads, freeze protection, and IAQ.
6. Create MeasureBrief and verification plan.

## Outputs
- ECM brief
- Sketchbox parameter map
- implementation and verification notes

## Guardrails
Do not report savings when prerequisites fail. Keep non-energy benefits separate from modeled energy.

## Validation
Evidence chain complete; parameter mapping reviewed; result passes QA.
