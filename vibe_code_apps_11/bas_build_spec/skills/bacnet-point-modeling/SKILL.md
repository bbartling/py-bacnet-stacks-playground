---
name: bacnet-point-modeling
description: >-
  Use when modeling BACnet points, object types (AI/AO/AV/BI/BO/BV/MSV…),
  instances, present-value, priority-array, COV, read/write/RPM, device discovery,
  or mapping field controllers to supervisory points. Triggers on: BACnet,
  bacpypes3, ObjectIdentifier, read_property, write_property, who-is, 47808,
  bacnet_scripts.md, VRF, DOAS, AHU, FCU.
---

# BACnet point modeling (supervisory layer)

## Repo references

- **`bas_build_spec/bacnet_scripts.md`** — working BACpypes3 patterns (client + sample devices).
- **`bas_build_spec/spec.md`** — domain `Point` fields, commandable flags, simulator vs real driver.
- **NIC / bind:** spec § BACNET / BACPYES3 — `--address IP/prefix[:47808]` on the interface that reaches the BACnet segment.

## Modeling rules

- Separate **protocol address** (device instance, MAC, IP:port) from **semantic role** (supply air temp, valve command, etc.).
- Prefer **normalized point records** in the app DB (object type + instance + device id + optional semantic tag / Brick link).
- Commandable points: track **writable priority**, **relinquish default**, and **priority array** when the product exposes them.

## Building program vs equipment taxonomy

The **field** may be VAV + central AHU, **VRF + DOAS**, **HP DOAS**, **CRAH** for data centers, **AHU + terminal reheat** for labs, **isolation rooms** for hospitals, etc. The supervisory model should accept **multiple equipment templates** per site; do not hardcode only “AHU + VAV” in persistence—use **equipment_type** + **point lists** driven by config or seeded templates.

## Related skills

- `safe-bacnet-writes` — operator writes and audit.
- `brick-schema-modeling` — semantic tagging of points/equipment.
- `bas-graphics` — what operators see for each template.
