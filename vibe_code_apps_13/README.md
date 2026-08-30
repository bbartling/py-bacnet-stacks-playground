# Checkpoint 13 - Rust BACnet MS/TP Router Appliance

**Status: Active** — Phase 1 wire-test + Phase 2 MS/TP software/loopback in-repo. **Phase 2 Rescue (2026-08-30):** Clause 9 CRC + USB stream pin `73a1fd4`; live BASRT/FEC bench exists. Hardware Gates 2–6 OPEN until `captures/` evidence. See [`docs/PHASE2_SOFTWARE_RESULTS.md`](docs/PHASE2_SOFTWARE_RESULTS.md) and [`docs/PHASE2_HARDWARE_RUNBOOK.md`](docs/PHASE2_HARDWARE_RUNBOOK.md).

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

Workspace pins `bbartling/rusty-bacnet` (fork) until upstream merges [#464](https://github.com/jscott3201/rusty-bacnet/pull/464):

```text
73a1fd41df7df2dfb3fa005cf339f347751f0286
```

Includes Clause 9.6 CRC polys (`0x81` / `0x8408`) and USB stream reassembly (`a9912b8`). Do not depend on a moving branch. Commit `Cargo.lock`. Re-pin to `jscott3201/rusty-bacnet` at the merge SHA when #464 lands.

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

