# Decision Log

## D-001 - Use Waveshare C for the primary bench

Status: accepted for lab baseline.

Use C+C first because the C model is FT232RNL, hardware auto-direction and explicitly isolated. Run B+B and B+C only after the baseline to test driver/chip portability.

## D-002 - Default to 38,400 bps

Status: accepted.

The CLI accepts the six standard rates documented in the clause checklist. The default is 38,400 bps for a conservative mixed-vendor starting point. Every hardware report records the selected rate.

## D-003 - No protocol in Phase 1

Status: accepted.

Raw alternating envelopes isolate USB, tty, UART, auto-direction and wiring behavior. BACnet code begins only after the hardware gate.

## D-004 - Phase 2 is MS/TP only

Status: accepted.

Reuse the upstream mini-device's object/service behavior, not its B/IP socket setup. The resulting executable has no IP transport or IP-facing CLI.

## D-005 - Phase 3 router is not the Phase 2 device

Status: accepted.

The router participates on MS/TP as a master routing port and forwards NPDUs. It does not expose the Phase 2 points.

## D-006 - Use current `AnyTransport`

Status: accepted subject to pinned-source verification.

The reviewed Rust `dev` snapshot includes a mixed-transport wrapper. Do not build a duplicate enum unless the pinned API changes or a measured defect requires it.

## D-007 - Extended MS/TP blocks a router-conformance claim

Status: accepted.

Phase 3 must implement/test COBS/CRC-32K extended frames before claiming ANSI/ASHRAE 135-2020 router compliance. Standard-frame routing may be used as an explicitly limited intermediate prototype.

## D-008 - Stack ownership (production vs research vs oracle)

Status: accepted (2026-08-29).

| Stack | Role |
|-------|------|
| **rusty-bacnet** (pinned git rev) | Production MS/TP + BACnet for Vibe13 apps (`mstp-lab`, `mstp-fec-diag`, mini-device) |
| **Coleman / other research** | Research only — not the production transport |
| **bacnet-stack (C)** | External receive-only oracle (`mstpcap`) — sibling checkout, never vendored large trees |
| **lab-common** | Stack-neutral baud/envelope/config validation |
| **mstp-lab** | Thin rusty-bacnet boundary (transport open, acceptance reports) |

Do not copy large upstream trees into this repo. Phase 3 router waits until Phase 2 hardware gates pass.

## D-009 - Midspan USB vs end-of-line adapter

Status: accepted (2026-08-29 hardware).

Waveshare midspan was previously the probe point; current bench places the USB RS-485 adapter at **end-of-line** with JCI FEC mid-daisy-chain and Workbench online. Probe MAC remains **3** (never 0 while BASRT is MAC 0). Physical topology notes belong in hardware runbooks, not product code.

## D-010 - USB host gaps are not Clause 9 T_frame_abort

Status: accepted pending upstream merge.

Async USB/serial read chunk gaps must not clear MS/TP reassembly buffers using wire `T_frame_abort` (~1.56 ms @ 38400). Host reassembly uses a named stale-partial policy; token state-machine timers stay separate. Tracked in sibling `~/src/rusty-bacnet-vibe13` branch `fix/mstp-usb-stream-decoder` (local commit; push only with human OK).


