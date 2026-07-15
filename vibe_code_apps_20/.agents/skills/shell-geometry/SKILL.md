# Shell Geometry

## Purpose
Translate real buildings into the minimum defensible rectangular EnergyPlus shells.

## Invoke when
Geometry, faÃ§ade, glazing, floor, or mixed-use modeling tasks.

## Required inputs
- Gross and conditioned areas
- floors and heights
- aspect ratio or dimensions
- faÃ§ade glazing
- attachments/adjacencies
- HVAC/program partitions

## Procedure
1. Start with one shell.
2. Split only for material differences.
3. Reconcile shell floor areas.
4. Represent attachments to avoid overstating exterior exposure.
5. Record faÃ§ade WWR and unknowns.
6. Produce a geometry sketch table.

## Outputs
- shell schedule
- geometry assumptions
- WWR table

## Guardrails
Do not model individual rooms. Do not use shell count to mimic zoning detail unsupported by the tool.

## Validation
Area reconciliation; exterior exposure sanity check; shell rationale present.
