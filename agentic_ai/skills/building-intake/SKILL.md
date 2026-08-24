---
name: building-intake
description: Create a source-traceable, privacy-aware building profile before EnergyPlus modeling, calibration, or control studies.
---

# Building intake

Use this before a new building enters the shared workflow.

1. Record conditioned area, use, location/time zone, geometry, envelope, HVAC topology, schedules, utility context, and data coverage.
2. Give each material value a status: `SOURCE_FACT`, `INFERRED_FROM_DATA`, `ENGINEERING_ASSUMPTION`, or `UNRESOLVED`.
3. Normalize units and reconcile floor/shell areas before model authoring.
4. Keep a missing-input list; do not fill it with silent defaults.
5. If the project is anonymized, use stable pseudonyms and remove addresses, coordinates, account identifiers, owner names, and identifying screenshots.

Produce a profile, an evidence/assumption ledger, and a redaction log when applicable. Model only the number of shells/zones needed to preserve material loads, schedules, and HVAC/control distinctions.
