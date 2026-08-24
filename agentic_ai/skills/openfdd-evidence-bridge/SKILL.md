---
name: openfdd-evidence-bridge
description: Turn Open-FDD or Vibe 19 exports into traceable evidence and candidate modeling/RCx measures without treating rule hits as proof of savings.
---

# Open-FDD evidence bridge

Use this when a Vibe 19/Open-FDD export informs EnergyPlus or an RCx workflow.

1. Preserve the exported package, rule version, source interval, equipment mapping, and anonymization state.
2. Convert rule hits to normalized observations; retain false-positive/review status rather than promoting every hit to a fault.
3. Map accepted findings to an evidence record and, when appropriate, a measure brief. Examples include runtime, comfort, economizer, airflow/damper, sensor health, PID hunting, and static-pressure evidence.
4. Require measured context and a reviewer for causality claims. FDD findings can prioritize model inputs or ECMs; they do not directly prove utility savings.

Use `evidence-and-measures` for the record/brief contract and `energyplus-model-authoring` for any resulting model change.
