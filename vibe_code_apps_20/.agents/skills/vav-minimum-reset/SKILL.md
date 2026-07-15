# VAV Minimum Flow Reset

## Purpose
Translate evidence of excess minimum airflow and reheat into a defensible individual ECM.

## Invoke when
When evidence suggests excess minimum airflow and reheat.

## Required inputs
- airflow/SP, occupancy, CO2 where applicable, reheat
- approved baseline
- implementation constraints

## Procedure
1. Validate sensors and prerequisites.
2. Confirm applicability and causal mechanism.
3. Quantify affected hours/loads without double counting.
4. Define exact baseline and proposed inputs.
5. Preserve ventilation and pressurization requirements; separate fixed-minimum correction from DCV.
6. Create MeasureBrief and verification plan.

## Outputs
- ECM brief
- Sketchbox parameter map
- implementation and verification notes

## Guardrails
Do not report savings when prerequisites fail. Keep non-energy benefits separate from modeled energy.

## Validation
Evidence chain complete; parameter mapping reviewed; result passes QA.
