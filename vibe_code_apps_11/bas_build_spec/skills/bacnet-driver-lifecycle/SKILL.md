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

1. Human sets **this host’s** BACnet NIC bind (not the field device IP) and runs discovery (example):

   ```bash
   cd /home/ben
   python3 bas_build_spec/bacnet_scripts_example/point_discovery.py \
     --name BensReadApp --instance 100 --address 192.168.204.18/24:47808 --debug
   ```

   Expect **I-Am** replies and per-device **`object-list`** lines from **bacpypes3** (see script header). If zero I-Am, fix VLAN/firewall/bind before automation claims BACnet.

2. Optional **cron worker** (after env is set in `cron_codex/.env`): `bas_bacnet_lab_verify.sh` appends redacted summaries to **`memory/integrations/bacnet.md`**. Enable only when `BAS_BACNET_LAB_VERIFY=true` and `BAS_BACNET_*` bind vars are filled.

3. The tech **signs off** in **`BUILD_CHECKPOINTS.md`** and **`memory/integrations/bacnet.md`**: date, bind used, **device instance + pduSource** pairs, object-list counts vs expectation.

4. Until sign-off exists, keep **`bas_app`** on **simulator**; hourly Codex may continue UI/API work. Do not enable live driver flags or mark acceptance rows for on-wire BACnet.

## Phase 2 — AI / automation: structured discovery artifact

**Goal:** Machine-readable inventory beyond a one-off script (for `bas_app` and tests).

- Extend or add scripts under **`bas_build_spec/bacnet_scripts_example/`** (or a future `bas_app` poller package) to emit **JSON** (devices, `object-list`, optional `object-name` / `present-value` samples) — **no credentials in repo**.
- Keep **Who-Is** bounds valid: **high_limit ≤ 4194303**.
- Store generated artifacts under **`.gitignore`** if they are large or environment-specific; commit only **schemas** or **small fixtures** if needed for CI.

## Phase 3 — AI: driver framework (BACpypes3)

**Goal:** A **replaceable** driver package under **`bas_app`** (poll/COV adapters, config, health) mirroring **`bacnet_scripts.md`**: **ReadProperty**, **WriteProperty** (with priority), **relinquish (write Null)**, **ReadPropertyMultiple** where appropriate. Supervisor domain services stay interface-driven so simulator and driver swap without UI rewrites.

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
