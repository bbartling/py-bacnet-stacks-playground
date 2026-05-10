---
name: alarm-workflows
description: >-
  Use when implementing alarms, priorities, ack/shelve, alarm history, routing
  from alarm to equipment graphic, stale/offline/comm loss, or command vs status
  mismatch. Triggers on: alarm, acknowledge, shelve, severity, RTN, alarm banner,
  lifecycle, BACnet fault.
---

# Alarm workflows

## Spec / checklist anchors

- **`bas_build_spec/spec.md`** — alarm types, lifecycle, UI requirements.
- **`bas_build_spec/acceptance_criteria.md`** — Alarms section.

## BACnet alignment

- Surface **protocol alarms** (where available) and **supervisory** rules (high/low, stale, mismatch) consistently.
- Navigation: alarm row → equipment / point context for operator response.

## Related skills

- `safe-bacnet-writes` — if alarms interact with overrides or writes.
- `trend-data` — alarm correlation with trends.
- `bas-graphics` — deep-link targets from alarm UI.
