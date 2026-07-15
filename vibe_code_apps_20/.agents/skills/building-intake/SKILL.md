# Building Intake

## Purpose
Create an identity-safe, traceable BuildingProfile before modeling.

## Invoke when
Starting a project, importing owner data, or preparing a baseline.

## Required inputs
- Conditioned area
- building use
- climate/location choice
- envelope summary
- HVAC summary
- schedules
- utility context
- anonymization flag

## Procedure
1. Separate known facts from assumptions.
2. Normalize units.
3. Create shell candidates based on materially different geometry, program, schedule, or HVAC.
4. Record provenance and confidence for each critical input.
5. Emit missing-input list.

## Outputs
- `building_profile.json`
- intake summary
- missing-input list

## Guardrails
Do not expose address when anonymized. Do not infer energy code solely from city without review.

## Validation
Schema validates; floor area is positive; shell areas reconcile to building area within tolerance.
