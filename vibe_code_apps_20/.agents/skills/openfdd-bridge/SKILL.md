# Open-FDD / Vibe 19 Bridge

## Purpose
Convert deterministic FDD analytics into evidence-backed ECM candidates.

## Invoke when
Reading `fdd_summary.csv`, session exports, role maps, fault hours, or RCx analytics.

## Required inputs
- Vibe 19 exports
- rule registry
- role mappings
- equipment metadata
- schedules and weather context

## Procedure
1. Validate package and mappings.
2. Normalize equipment IDs and rule IDs.
3. Convert findings into EvidenceRecords.
4. Apply motor/plant/occupancy gates.
5. Group related evidence without double counting.
6. Generate candidate ECMs with prerequisites.
7. Route each candidate to a domain skill.

## Outputs
- evidence JSONL
- candidate ECM JSON
- rejected-candidate log

## Guardrails
A fault is not savings. Sensor-validation failures block dependent control ECMs unless corrected.

## Vibe19 → Sketchbox maps (starter)

| FDD / RCx signal | ECM skill | Example concept |
| --- | --- | --- |
| `SCHED-247` continuous runtime | `schedule-optimization` | Madison AHU-2 24/7 → occupied schedule |
| `AHU-DUCTHI` / `FC1` | `duct-static-reset` | Static reset both AHUs after schedule ECM |
| Comfort / SAT faults | `sat-reset` / `vav-minimum-reset` | Only with sensor health gates |

See `docs/FDD_TO_SKETCHBOX_WORKFLOW.md` and `examples/buildings/madison_liberty_concept.json`.

## Validation
Every candidate cites evidence; missing roles remain explicit; rejected candidates have reasons.
