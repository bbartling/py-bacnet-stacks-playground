# Heating and Cooling Plant Efficiency

## Purpose
Translate evidence of equipment efficiency or plant replacement into a defensible individual ECM.

## Invoke when
When evidence suggests equipment efficiency or plant replacement.

## Required inputs
- capacity, efficiency curves/ratings, fuel, staging, runtime
- approved baseline
- implementation constraints

## Procedure
1. Validate sensors and prerequisites.
2. Confirm applicability and causal mechanism.
3. Quantify affected hours/loads without double counting.
4. Define exact baseline and proposed inputs.
5. Use correct rating basis and document redundancy versus active capacity.
6. Create MeasureBrief and verification plan.

## Outputs
- ECM brief
- EnergyPlus parameter map
- implementation and verification notes

## Guardrails
Do not report savings when prerequisites fail. Keep non-energy benefits separate from modeled energy.

## Validation
Evidence chain complete; parameter mapping reviewed; result passes QA.
