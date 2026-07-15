# Duct Static Pressure Reset

## Purpose
Translate evidence of excess static pressure or persistent terminal damper margin into a defensible individual ECM.

## Invoke when
When evidence suggests excess static pressure or persistent terminal damper margin.

## Required inputs
- duct pressure/SP, VAV damper positions, fan speed/power
- approved baseline
- implementation constraints

## Procedure
1. Validate sensors and prerequisites.
2. Confirm applicability and causal mechanism.
3. Quantify affected hours/loads without double counting.
4. Define exact baseline and proposed inputs.
5. Model fan-power improvement only after confirming terminal control and critical-zone logic.
6. Create MeasureBrief and verification plan.

## Outputs
- ECM brief
- EnergyPlus parameter map
- implementation and verification notes

## Guardrails
Do not report savings when prerequisites fail. Keep non-energy benefits separate from modeled energy.

## Validation
Evidence chain complete; parameter mapping reviewed; result passes QA.
