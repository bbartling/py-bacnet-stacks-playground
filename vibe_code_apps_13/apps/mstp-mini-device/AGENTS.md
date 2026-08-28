# Phase 2 Mini-Device Agent Rules

Read the root `AGENTS.md` and `docs/PHASE_2_MSTP_MINI_DEVICE.md` first.

## Hard identity

This is a BACnet MS/TP application device. It uses one `MstpTransport` and one tty. It is not a BACnet/IP device, router, BBMD or web application.

## Reuse from upstream sample

Reuse object/service behavior and tests from `mini-device-revisited`. Delete/replace its network configuration and B/IP construction. Inspect the pinned source and build a transport-generic `BACnetServer` entry point if needed.

## Forbidden in this subtree

- `BipTransport`, `bip_builder`, UDP, `socket2`, `UdpSocket`;
- IP/NIC/broadcast/port 47808 configuration;
- BBMD, FDR, HTTP, web or router code;
- copying the MS/TP state machine;
- claiming extended-frame support without vectors and interop evidence.

Add a CI guard for forbidden imports/features and review the final dependency tree. SSH into the host is permitted operational management, not part of BACnet transport.

## Definition of done

The two-adapter bench shows token passing and the complete device acceptance sequence, including negative cases, restart admission, 500 repeated reads and a one-hour soak. The executable exposes no B/IP surface.

