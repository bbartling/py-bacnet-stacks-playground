# Fan Power Improvement

## Purpose
Translate evidence of high fan power, poor efficiency, or VFD opportunity into a defensible individual ECM.

## Invoke when
When evidence suggests high fan power, poor efficiency, or VFD opportunity.

## Required inputs
- CFM, fan kW/HP, static pressure, efficiency, runtime
- approved baseline
- implementation constraints

## Procedure
1. Validate sensors and prerequisites.
2. Confirm applicability and causal mechanism.
3. Quantify affected hours/loads without double counting.
4. Define exact baseline and proposed inputs.
5. Map to fan-power parameter with explicit combined/supply/return basis.
6. Create MeasureBrief and verification plan.

## Outputs
- ECM brief
- EnergyPlus parameter map
- implementation and verification notes

## Guardrails
Do not report savings when prerequisites fail. Keep non-energy benefits separate from modeled energy.

## Validation
Evidence chain complete; parameter mapping reviewed; result passes QA.
