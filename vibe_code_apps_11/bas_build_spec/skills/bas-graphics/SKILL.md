---
name: bas-graphics
description: >-
  Use when building operator graphics, equipment synoptic pages, SVG/HMI-style
  layouts, live value bindings, or navigation from graphic to point detail.
  Triggers on: graphic, synoptic, dashboard, AHU, VAV, DOAS, VRF, CRAH, chiller,
  plant, room, dark theme, graphic.html.
---

# BAS graphics (building-program aware)

## Visual theme

- **App shell / schedules:** follow **`frontend_example/schedule_example.html`** tokens and density (see spec § DESIGN STYLE).
- **Synoptic / wire-sheet panes:** **`frontend_example/graphic.html`** — layout patterns, gauge strips, BAS status color semantics (see spec § DESIGN STYLE).

## HVAC / building type

Graphics must be **data-driven**, not locked to a single archetype:

- Support **multiple templates** seeded or configured per **building program** (office VAV + AHU, **VRF + DOAS**, **HP DOAS**, data-center **CRAH / chilled water**, **lab** pressurization / ACH, **hospital** isolation OR, etc.).
- Each template binds to **points and equipment** from the domain model (BACnet or simulator). If a site has no chiller, the plant graphic **omits or collapses** that region—no hardcoded empty placeholders required in acceptance testing beyond “template renders without error.”

## Interaction

- Live values without full page reload (SSE/WebSocket or equivalent).
- Links from equipment graphic → properties, trends, schedules, alarms.
- Authorized roles: start **safe command / setpoint** workflow from the graphic.

## Related skills

- `web-app-bas`
- `bacnet-point-modeling`
- `bacnet-schedule-motor-verify`
- `alarm-workflows`
