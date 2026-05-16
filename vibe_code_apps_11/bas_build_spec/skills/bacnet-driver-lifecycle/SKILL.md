---
name: bacnet-driver-lifecycle
description: >-
  Gated BACnet lab discovery, human-validated bind args, BACpypes3 examples in
  bacnet_scripts_example/, long-lived driver in bas_app, simulator default until
  sign-off. Triggers on: BACnet, Who-Is, I-Am, BBMD, driver, lab verify.
---

# BACnet driver lifecycle

## Default

- Runtime uses **simulator** until lab gate passes **or** autonomous commissioning is enabled (below).

## Autonomous commissioning (`BAS_BACNET_AUTO_COMMISSION=true`)

For a **commissioning head-end** where the operator wants wire on without manual gates each wake:

1. Set **`BAS_BACNET_AUTO_COMMISSION=true`** in `cron_codex/.env` (see `env.example`).
2. Keep **`PHASE_NOTEPAD.md` § A** (bind) and **§ C** (devices) filled — canonical site facts.
3. Worker **`bas_bacnet_auto_commission.sh`** runs every **5 min** (job `bas-bacnet-auto-commission`) and at the **start of each `bas_wake.sh`**: marks sign-off, writes `bacnet_wire_authorized`, merges `.env`, enables `bas-bacnet-discovery-poll`, runs Who-Is.
4. **Codex** (`bas_wake.sh` on cron) implements operator requests: **device tree** UI, **point reads**, **bacnet_scripts_example/** changes, and **any `cron/jobs.json` task** (intervals, enable/disable). Workers handle routine Who-Is between wakes.

**Disable** on production handoff: set `BAS_BACNET_AUTO_COMMISSION=false`, remove `state/bacnet_wire_authorized`, disable poll jobs.

## Manual gate (no auto flag)

- Scheduled Codex wakes **must not** run wire discovery unless `BUILD_CHECKPOINTS` explicitly calls for lab work **and** humans accept network risk.

## Rough-in UI vs wire BACnet (common confusion)

When the operator asks to **“start polling”** or **“populate with real data”**, respond with **Who-Is after lab sign-off** — not more simulator-labeled UI. The public rough-in page must **not** display “Simulator-only path” or `simulator_only` to operators (see **`field-commissioning-phases/references/commissioning-ui-language.md`**). Internal state may remain `simulator_only` until wire is enabled; **map to operator labels** in the public API/UI.

**After human lab sign-off** (see below), the **first wire step** is a controlled **Who-Is** on the bind in **`PHASE_NOTEPAD.md` § A** (NIC that reaches the OT segment), using **`bacnet_scripts_example/`** or `bas_bacnet_lab_verify.sh`. Record results in **`memory/integrations/bacnet.md`**. Cross-check I-Ams against **§ C** — operator chat may contain typos; notepad is canonical.

## Lab gate

1. Human sets `BAS_BACNET_*` bind variables (see `bacnet_scripts_example/` and `human_validated_args.env.example` when present).
2. Run discovery via documented worker (`bas_bacnet_lab_verify.sh` when wired) or a controlled mini.
3. Append results to **`memory/integrations/bacnet.md`** with instances, addresses, and expected object counts.
4. Record **human sign-off** in **`BUILD_CHECKPOINTS.md`** under **§ BACnet lab sign-off (human only)** before enabling Who-Is, bind, or field polling in `bas_app`.
5. **Who-Is** runs only after that sign-off, on the validated bind — never from a blind scheduled wake.

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
