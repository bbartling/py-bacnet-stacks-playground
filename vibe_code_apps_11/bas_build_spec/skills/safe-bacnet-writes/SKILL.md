---
name: safe-bacnet-writes
description: >-
  Use when implementing or reviewing supervisory writes, BACnet priorities,
  relinquish/null, confirmation + reason, audit trail, RBAC for commands, or
  disabling real field writes by default. Triggers on: write_property, command,
  override, priority 16, audit log, ReadOnly, simulator only, driver flag.
---

# Safe BACnet / supervisory writes

## Rules (non-negotiable)

- Real BACnet driver **off by default**; explicit config to enable (per spec).
- Authenticated user; **server-side** permission checks.
- Confirmation + **reason/comment**; **audit** every change and release.
- Commandable points only; show **commanded / overridden** state in UI.

## References

- **`bas_build_spec/spec.md`** — safe command workflow, safety section.
- **`bas_build_spec/bacnet_scripts.md`** — write + relinquish examples (BACpypes3).

## Related skills

- `bacnet-driver-lifecycle` (lab gate before enabling real writes on wire)
- `bacnet-point-modeling`
- `alarm-workflows`
- `web-app-bas`
