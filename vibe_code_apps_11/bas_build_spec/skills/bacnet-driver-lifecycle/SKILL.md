---
name: bacnet-driver-lifecycle
description: >-
  Gated BACnet lab discovery, human-validated bind args, BACpypes3 examples in
  bacnet_scripts_example/, long-lived driver in bas_app, simulator default until
  sign-off. Triggers on: BACnet, Who-Is, I-Am, BBMD, driver, lab verify.
---

# BACnet driver lifecycle

## Default

- Runtime uses **simulator** until lab gate passes.
- Scheduled Codex wakes **must not** run wire discovery unless `BUILD_CHECKPOINTS` explicitly calls for lab work **and** humans accept network risk.

## Lab gate

1. Human sets `BAS_BACNET_*` bind variables (see `bacnet_scripts_example/` and `human_validated_args.env.example` when present).
2. Run discovery via documented worker (`bas_bacnet_lab_verify.sh` when wired) or a controlled mini.
3. Append results to **`memory/integrations/bacnet.md`** with instances, addresses, and expected object counts.
4. Record **human sign-off** in **`BUILD_CHECKPOINTS.md`** before claiming “live BACnet verified.”

## Examples index

Scripts live under **`bas_build_spec/bacnet_scripts_example/`** (Who-Is / object-list, read/write/release, schedules, weather gateway). See **`references/bacnet_scripts_index.md`**.

## Driver in bas_app (Codex)

- Extend the **long-lived** BACpypes3 driver using the **same** validated bind args as the lab scripts.
- Operator **write** flows must follow **`safe-bacnet-writes`** (confirmation, reason, audit, RBAC, relinquish semantics).

## Validation (Cursor)

- Confirm `BAS_BACNET_LAB_VERIFY` is off in `.env` unless lab is intentional.
- `bas_validate_wake_pass.sh` reports BACnet posture; do not enable wire traffic from Cursor.

## Related skills

- `bacnet-point-modeling`, `safe-bacnet-writes`, `workspace-memory`, `spec-validation`
