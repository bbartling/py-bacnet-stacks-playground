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

