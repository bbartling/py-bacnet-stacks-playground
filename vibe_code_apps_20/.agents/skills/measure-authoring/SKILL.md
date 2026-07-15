# Measure Authoring

## Purpose
Create an exact, reviewable MeasureBrief before touching Sketchbox.

## Invoke when
Any ECM is proposed or modified.

## Required inputs
- Approved evidence
- baseline parameters
- proposed parameters
- Sketchbox mapping
- implementation notes

## Procedure
1. State condition and causal mechanism.
2. Run applicability gates.
3. Define exact baseline/proposed values.
4. Identify Sketchbox tab/group/parameter.
5. List interactions and non-modeled benefits.
6. Request approval.

## Outputs
- measure brief JSON/Markdown
- review decision

## Guardrails
One measure brief must represent one coherent intervention. Do not hide multiple control changes under a vague title.

## Validation
Schema validates; every proposed change has baseline value, units, provenance, and reviewer.
