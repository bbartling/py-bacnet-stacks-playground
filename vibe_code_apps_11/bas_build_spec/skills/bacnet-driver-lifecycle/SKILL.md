---
name: bacnet-driver-lifecycle
description: >-
  Use when adding real BACnet lab work after simulator-only baselines: human
  sign-off on discovery output, Who-Is/I-Am/object-list sweeps, implementing a
  BACpypes3 driver from bacnet_scripts.md (read, write, relinquish, RPM), feature
  flags, then wiring bas_app to the driver. Triggers on: point_discovery,
  who-is, I-Am, object-list, 4194303, driver lifecycle, lab gate, bacpypes3,
  ENABLE_BACNET, bacnet_scripts_example, bacnet_scripts.md.
---

# BACnet driver lifecycle (lab → driver → web app)

## References

- **`bas_build_spec/bacnet_scripts.md`** — patterns: read / write / write-null / RPM / priority array (copy shapes from here; do not paste the whole file into prompts).
- **`bas_build_spec/bacnet_scripts_example/point_discovery.py`** — runnable **Who-Is → I-Am → per-device `object-list`** sweep; BACnet device instance range **0..4194303** (bacpypes3 enforces this).
- **`bas_build_spec/spec.md`** — § BACNET / NIC bind (`--address IP/prefix[:47808]` on the interface that reaches the segment).
- **`bas_app/backend/README.md`** — default stack is **simulator-only** until checkpoints explicitly enable lab BACnet.

## Phase 0 — Lab prerequisites (human + network)

- Correct **`--address`** bind on the NIC that sees the controllers; UDP **47808** open; no production writes without ops approval.
- Optional: capture **`point_discovery.py`** (or equivalent) output to a **log file** in-repo only if it contains **no secrets** (prefer redacted summaries in **`BUILD_CHECKPOINTS.md`** per **`GUARDRAILS.md`**).

## Phase 1 — Human gate (required before “real driver” work)

**Goal:** A technician confirms on-wire inventory matches **expected** controllers (device instances, IP sources, object counts).

1. Run discovery from a known-good host (example):

   ```bash
   cd /home/ben
   python3 bas_build_spec/bacnet_scripts_example/point_discovery.py \
     --name BensReadApp --instance 100 --address <BIND_IP>/24:47808
   ```

2. The tech **signs off** in **`bas_build_spec/BUILD_CHECKPOINTS.md`** (e.g. under **Done recently**): date, bind address used, list of **device instance + pduSource** pairs, and “object-list counts look expected” (or note discrepancies).

3. Until this sign-off exists, **do not** mark acceptance rows that claim live BACnet verification, and **do not** enable a real-driver feature flag in production config.

## Phase 2 — AI / automation: structured discovery artifact

**Goal:** Machine-readable inventory beyond a one-off script (for `bas_app` and tests).

- Extend or add scripts under **`bas_build_spec/bacnet_scripts_example/`** (or a future `bas_app` poller package) to emit **JSON** (devices, `object-list`, optional `object-name` / `present-value` samples) — **no credentials in repo**.
- Keep **Who-Is** bounds valid: **high_limit ≤ 4194303**.
- Store generated artifacts under **`.gitignore`** if they are large or environment-specific; commit only **schemas** or **small fixtures** if needed for CI.

## Phase 3 — AI: driver implementation (BACpypes3)

**Goal:** A **replaceable** driver module (sidecar or in-process) that mirrors patterns in **`bacnet_scripts.md`**: **ReadProperty**, **WriteProperty** (with priority), **relinquish (write Null)**, **ReadPropertyMultiple** where appropriate.

- **Interface first:** supervisory **`bas_app`** domain stays on a **`BacnetPointSource`** (or existing simulator interface) — swap simulator ↔ driver via **config / feature flag**.
- **Default off:** real stack remains **simulator-only** unless **`BUILD_CHECKPOINTS`** and **`.env`** (or equivalent) explicitly enable lab BACnet.
- **Tests:** unit tests with **fakes** or **recorded JSON**; optional integration job **only** on lab hosts after Phase 1 sign-off.

## Phase 4 — Web app (`bas_app`)

**Goal:** UI and APIs show **live** values when the driver is enabled; unchanged simulator path otherwise.

- API routes read through the **same** domain services used for demo data; only the **adapter** changes.
- Operator **write** flows must follow **`safe-bacnet-writes`** (confirmation, reason, audit, RBAC, relinquish semantics).

## Related skills

- **`bacnet-point-modeling`** — point records, COV, semantic mapping.
- **`safe-bacnet-writes`** — supervisory command safety.
- **`web-app-bas`** — head-end UI/API and dial-in.
- **`brick-schema-modeling`** — optional semantic tags after points exist.
