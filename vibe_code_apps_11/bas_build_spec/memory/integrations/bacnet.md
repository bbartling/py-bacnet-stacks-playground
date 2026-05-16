# BACnet integration memory

**Per-site log** — not generic spec. **Wire off** until human lab sign-off in `BUILD_CHECKPOINTS.md` § BACnet lab sign-off. After sign-off: **Who-Is** on bind from **`PHASE_NOTEPAD.md` § A**; record I-Ams, bind args, and object counts here per **bacnet-driver-lifecycle**.

## Operator-staged devices (unverified — not from Who-Is)

| Role | BACnet device ID | IPv4 | Notes |
|------|------------------|------|--------|
| Head-end bind | (local) | `192.168.204.18/24:47808` on `enp3s0` | BACpypes3 `--address` target |
| VAV | `3456790` | `192.168.204.14` | Expected on wire |
| AHU | `3456789` | **`192.168.204.13`** | **Corrected** — chat had typo `.113` |

- [ ] Human sign-off on discovery (instances, addresses, counts) — **Who-Is not run yet**
- [ ] Who-Is log appended here after sign-off (I-Am list, instance ↔ IP)
