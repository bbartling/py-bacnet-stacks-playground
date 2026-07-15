# Data Contract

## Authoritative objects

### BuildingProfile
Identity-safe building description, conditioned area, shells, programs, schedules, HVAC, envelope, utility and climate assumptions.

### EvidenceRecord
A single observed or documented fact supporting an ECM.

### ECMCandidate
A hypothesis connecting evidence to a controllable or capital measure.

### MeasureBrief
Human-reviewable specification of exact baseline/proposed changes in Sketchbox terminology.

### ModelRun
A baseline or measure execution with immutable input fingerprint and exported results.

### ResultRecord
Annual/monthly energy, cost, emissions, demand where available, plus quality flags.

## Provenance values

- `design_document`
- `equipment_schedule`
- `bas_trend`
- `openfdd_rule`
- `site_observation`
- `utility_bill`
- `engineer_inference`
- `sketchbox_default`
- `rule_of_thumb`

## Null handling

Unknown values remain null and carry `NEEDS_INPUT`. Do not use zero unless zero is physically and semantically correct.
