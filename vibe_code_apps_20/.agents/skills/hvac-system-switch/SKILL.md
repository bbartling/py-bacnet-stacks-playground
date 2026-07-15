# HVAC System Switch

## Purpose
Translate evidence of electrification or major HVAC conversion into a defensible individual ECM.

## Invoke when
When evidence suggests electrification or major HVAC conversion.

## Required inputs
- existing/proposed system types, fuel, DOAS, efficiencies
- approved baseline
- implementation constraints

## Procedure
1. Validate sensors and prerequisites.
2. Confirm applicability and causal mechanism.
3. Quantify affected hours/loads without double counting.
4. Define exact baseline and proposed inputs.
5. Use EnergyPlus custom HVAC system type measure where supported and document unmatched features.
6. Create MeasureBrief and verification plan.

## Outputs
- ECM brief
- EnergyPlus parameter map
- implementation and verification notes

## Guardrails
Do not report savings when prerequisites fail. Keep non-energy benefits separate from modeled energy.

## Validation
Evidence chain complete; parameter mapping reviewed; result passes QA.
