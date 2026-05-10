---
name: brick-schema-modeling
description: >-
  Use when mapping BAS points or equipment to BRICK/RDF (or a slim internal
  ontology compatible with Brick), relationships (feeds/isPartOf/hasPoint),
  tagging for analytics, or cross-building queries. Triggers on: Brick, RDF,
  ontology, hasPoint, Equipment, Point, VAV, AHU, Chiller, DOAS, CRAH, Room,
  lab pressurization, hospital isolation.
---

# BRICK / semantic schema modeling

## Goal

Give **stable semantic names** to BACnet-backed (or simulated) points so graphics, alarms, and trends stay correct when the **HVAC archetype** changes (VRF DOAS vs VAV vs data-center CRAH).

## Practices

- Prefer **Equipment** → **hasPoint** → **Point** patterns aligned with [Brick](https://brickschema.org/) where the team adopts Brick; otherwise define a **minimal internal enum** (`semantic_tag`) that can be exported to Brick later.
- Keep **BACnet object id** as the transport key; Brick (or tags) as **presentation + analytics** layer.
- Document equivalences (e.g. `Supply_Air_Temperature_Sensor` vs site-specific label) in `references/` if tables grow large.

## Optional layout

```
brick-schema-modeling/
  SKILL.md
  references/
    vocabulary-notes.md   # optional: site-specific tag table
```

## Related skills

- `bacnet-point-modeling`
- `trend-data`
- `bas-graphics`
