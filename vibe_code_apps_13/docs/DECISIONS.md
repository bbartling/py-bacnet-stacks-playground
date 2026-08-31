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

Status: accepted (implemented upstream-capable; awaiting merge).

Async USB/serial read chunk gaps must not clear MS/TP reassembly buffers using wire `T_frame_abort` (~1.56 ms @ 38400). Host reassembly uses a named stale-partial policy; token state-machine timers stay separate. Commit `a9912b8` on `fix/mstp-clause9-crc` / PR [#464](https://github.com/jscott3201/rusty-bacnet/pull/464).

## D-011 - Clause 9 CRC was the primary MS/TP interoperability blocker

Status: accepted (2026-08-30).

Prior diagnosis that header CRC `0x37` on Token `55 FF 00 00 07 00 00 37` was “invalid” was **wrong**. `CRC8([00,00,07,00,00]) == 0x37` under Clause 9.6. rusty-bacnet previously used reflected polys `0xE0` / `0xA001` (self-round-trip green, live trunk reject). Correct polys: header `0x81`, data `0x8408`. Commit `6a70b85`. `latency_timer` affects host latency but does not make `0x37` invalid.

## D-012 - PR #126 merged; old USB-only Cursor plan is historical

Status: accepted (2026-08-30).

`develop` includes merge `eb178f70` (PR #126). The attached Cursor plan `vibe13_ms_tp_usb_fix_*` is historical. Active work follows the **Phase 2 Rescue** prompt (CRC → passive → FEC client → mini-device → shared endpoint → FEC mirror).


