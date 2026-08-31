# Checkpoint 13 - Rust BACnet MS/TP Router Appliance

**Status: Active** — Phase 2 on pin `af4e886` (`jscott3201/rusty-bacnet` dev; #467/#468 **merged**). Historical Gate 1–4 PASS on `19d205d` — **post-pin live smoke required**. Vibe13 retains Rust hardware mini-device; upstream Python example is binding-only. Gates 5–6 OPEN. See [`docs/PHASE2_SOFTWARE_RESULTS.md`](docs/PHASE2_SOFTWARE_RESULTS.md) and [`docs/PHASE2_HARDWARE_RUNBOOK.md`](docs/PHASE2_HARDWARE_RUNBOOK.md).

## Limitations (current)

- **Not a Clause 9 conformance claim** — CRC / USB stream / 9.5.6 token+PFM only.
- **No extended MS/TP frames** (types 32/33, COBS, CRC-32K) — do not claim router or oversized-frame conformance.
- **Gates 5–6 OPEN** — shared endpoint + soak not closed.
- **Host USB timing** — stale-partial timeout is scheduling-aware; not wire `T_frame_abort`.
- **Workbench nits** — Niagara Write=`readonly` facets, °C display vs BACnet degF (62), name slash → `MS.TP` are cosmetic / UI, not stack blockers.
- **Do not run open-fdd MQTT soaks** on the same Waveshare tty while mini-device owns the trunk.

## Linux resources (mstp-mini-device on live MS/TP)

Measured on **bensbench** (2026-08-30) while Gate 4 Workbench discovery was live — release binary, MAC 3, 38 400 baud, pin `e3b9edb` (behavior unchanged on `19d205d`):

| Metric | Value |
|--------|------:|
| Release binary size | ~4.9 MiB |
| Resident memory (VmRSS / HWM) | **~5.6 MiB** |
| Virtual size (VmSize) | ~404 MiB (mapped; not all resident) |
| Threads | 7 |
| CPU (steady, pidstat ~3 s) | **~1%** of one core (~0.3% usr / 0.7% sys) |
| Host | Linux 6.8 x86_64, 6 CPUs |

This is a **mega milestone**: a native Rust MS/TP master mini-device stays discoverable in JENEsys with **single-digit MiB RSS** and ~1% CPU while coexisting on the BASRT+FEC trunk.


This checkpoint develops a Linux x86 BACnet appliance in three strictly gated phases using two Waveshare USB TO RS485 (C) adapters and `rusty-bacnet`:

1. **Phase 1 - USB/RS-485 wire test:** prove both USB ports, adapters, wiring, serial settings, bidirectional bytes, timing, unplug behavior, and repeatable hardware tests. This phase contains no BACnet protocol.
2. **Phase 2 - MS/TP mini-device:** port the object model and application behavior from [`mini-device-revisited`](https://github.com/jscott3201/rusty-bacnet/tree/dev/examples/rust/samples/mini-device-revisited) to a native MS/TP transport. It is an MS/TP-only BACnet device. It has no BACnet/IP, UDP socket, IP address, broadcast address, BBMD, web server, or IP-side discovery.
3. **Phase 3 - router appliance:** route BACnet/IP network 100 to MS/TP network 2001 and add a small commissioning/diagnostic web application. The router's MS/TP port is a token-participating routing port, not the Phase 2 mini-device and not an MS/TP application device.

The original reservation README is preserved by the installer under `docs/reference/ORIGINAL_CHECKPOINT_README.md`.

## Start here

AI agents must read these files in order:

1. [`AGENTS.md`](AGENTS.md)
2. [`vibe13_agent_spec/SPEC.md`](vibe13_agent_spec/SPEC.md) — UI stack, repo map, agent commands
3. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
3. [`docs/BACNET_SPEC_CLAUSE_9_CHECKLIST.md`](docs/BACNET_SPEC_CLAUSE_9_CHECKLIST.md)
4. the active phase document under `docs/`
5. the phase-local `AGENTS.md` before changing an app directory

## Phase gates

| Phase | Required evidence before advancing |
|---|---|
| 1 | 10,000 alternating C-to-C raw exchanges at 38,400 bps with no missing, duplicate, or corrupt peer frames; clean unplug failure; unit tests retained in the project |
| 2 | Two real MS/TP masters exchange token and complete Who-Is/I-Am, RP, RPM, WP, relinquish, negative cases, restart tests, and a one-hour soak with no IP transport in the device binary |
| 3 | Routed Who-Is/I-Am, RP, RPM, WP, route discovery, hop-count and broadcast tests pass across B/IP -> router -> MS/TP; extended MS/TP is implemented and independently verified before the product claims 135-2020 router conformance |

No phase may be marked complete based only on compilation or simulated tests.

## Baud-rate policy

All serial-facing CLI/config surfaces accept exactly:

- 9,600 bps - required by ANSI/ASHRAE 135-2020;
- 19,200 bps - optional;
- 38,400 bps - required and the project default;
- 57,600 bps - optional and included because it appears in the standard;
- 76,800 bps - optional and commonly used on modern trunks;
- 115,200 bps - optional; validate every attached device and the physical segment.

The application must reject any other value unless a future decision record deliberately changes the policy.

## Hardware baseline

- Ubuntu x86 tower;
- two Waveshare USB TO RS485 (C), FT232RNL, hardware automatic direction, isolated;
- short A+ to A+, B- to B-, field-reference to field-reference bench segment;
- one 120-ohm termination at each physical end and no intermediate termination;
- verified network bias: at least one and no more than two BACnet-compliant bias sets;
- stable `/dev/serial/by-id/...` aliases;
- FTDI latency setting measured and recorded, with 1 ms used as the initial test value;
- 38,400 bps, 8 data bits, no parity, one stop bit.

The B/CH343G adapters are retained for B+B and B+C compatibility runs after the C+C baseline passes.

## Dependency snapshot

Workspace pins `jscott3201/rusty-bacnet` @ dev SHA (exact rev in `Cargo.toml` / `Cargo.lock`):

```text
af4e88680c51eb4da64dac47f0540a35bf184732
```

Includes merged #467 (CRC, USB reassembly, token/PFM) and #468 (Python MS/TP binding example). Vibe13 keeps its Rust hardware mini-device. Commit `Cargo.lock`.

## Initial workspace

The bootstrap includes a small, dependency-free `lab-common` Rust crate. It centralizes the approved baud values and validates MS/TP master/network configuration. Phase agents add application crates to the Cargo workspace only when their phase begins.

```bash
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
```

## Scope boundaries

- Checkpoint 13 is the integrated product path.
- The separate routing-research lab remains checkpoint 14.
- The Coleman kernel line discipline and `rusty-bacnet-mcp` are not dependencies of Phases 1-3.
- The BACnet specification PDF is licensed reference material. Do not copy or commit it into this repository.
- Vendor ID `999` in the upstream sample is a lab placeholder and must not ship.

