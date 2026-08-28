# AGENTS.md - Checkpoint 13 Engineering Contract

These instructions apply to every AI agent and every file below this directory. A deeper `AGENTS.md` adds phase-specific rules and takes precedence for that subtree.

## Mission

Build a trustworthy Linux BACnet/IP-to-MS/TP router appliance in three evidence-gated phases. Preserve the separation among raw serial validation, an MS/TP-only BACnet device, and the final router/web appliance.

## Mandatory reading before action

1. Read this file completely.
2. Read `README.md`, `docs/ARCHITECTURE.md`, and `docs/BACNET_SPEC_CLAUSE_9_CHECKLIST.md`.
3. Read the active phase plan and its local `AGENTS.md`.
4. Inspect the actual pinned `rusty-bacnet` source and compiler-visible APIs. Documentation and this plan do not override source.
5. Inspect the working tree and preserve user changes. Do not reset, clean, delete, or overwrite unrelated files.

## Phase boundaries

### Phase 1

Phase 1 is a raw physical/serial test. It must not import or implement BACnet, NPDU, APDU, BVLC, MS/TP framing, token passing, routing, UDP, or a web server. Its reusable parser, report, configuration validation, and failure tests belong in normal unit/integration tests.

### Phase 2

Phase 2 is a BACnet MS/TP application device only. Adapt the object database and services from `mini-device-revisited`, but remove its entire B/IP transport and networking setup.

The Phase 2 device must contain no:

- `BipTransport`, `BACnetClient::bip_builder`, or `BACnetServer::bip_builder`;
- UDP socket, `socket2`, `UdpSocket`, port 47808, NIC detection, IP address, subnet broadcast, BBMD, FDR, HTTP, or web UI;
- `--address`, `--broadcast`, `--port`, or other IP-facing CLI option.

SSH access to the Ubuntu host is operational administration and does not make the BACnet application a BACnet/IP device.

### Phase 3

Phase 3 is a router and management appliance. Its MS/TP port is a master station because it participates in token passing and forwards NPDUs. It must not reuse the Phase 2 object's AI/BI/AV/BV database or behave like that test device on the MS/TP network.

The router may later expose the BACnet Device/Network Port objects required by its actual PICS, but that is a distinct router-management implementation, not the Phase 2 mini-device.

## Source and dependency rules

- Start from the pinned source snapshot recorded in `README.md`; never ship a moving `dev` reference.
- Commit `Cargo.lock` for binaries.
- Prefer upstream APIs and small reviewed patches over copied/forked stack internals.
- The current `dev` source includes `bacnet_transport::any::AnyTransport` for heterogeneous B/IP + MS/TP router ports. Inspect and use it before creating another wrapper.
- The current MS/TP frame source does not yet implement Clause 9 extended frame types 32/33, COBS, and CRC-32K even though it accepts a 1497-byte maximum. Phase 3 may not claim router conformance or send oversized standard frames until that is fixed and independently tested.
- Do not introduce the Coleman kernel line discipline, Misty agent, or MCP server unless a later signed decision record changes scope.

## Baud and serial rules

- Accepted baud values: `9600`, `19200`, `38400`, `57600`, `76800`, `115200`.
- Default: `38400`.
- Reject other rates at CLI parsing/config validation; never silently round.
- Always configure 8N1 with flow control disabled.
- Select hardware automatic direction for Waveshare B/C USB adapters. Do not enable Linux RS-485 ioctl, RTS, or GPIO direction simultaneously.
- Use `/dev/serial/by-id/...`; do not persist `ttyUSB0`/`ttyACM0` assumptions.
- One process owns one tty. Fail clearly if a port is missing or busy.
- Bound every read, queue, parser buffer, retry, shutdown, and log history.

## BACnet Clause 9 gates

Implementation and tests must map to the clause checklist. In particular:

- exactly two endpoint terminations, 120 ohms +/-5%; no intermediate termination;
- verified bias network; do not assume the Waveshare onboard 120-ohm resistor also provides bias;
- 8N1 and accepted standard baud values;
- frame gap, frame abort, turnaround, post-drive, usage, reply, and no-token timings tested at every claimed baud;
- unique MS/TP MAC addresses and valid Max_Master/Max_Info_Frames;
- standard and extended frame lengths handled without truncation;
- router support for extended frames implemented before a 135-2020 routing claim.

## Testing discipline

Use four test labels:

- `unit`: no OS device or network required;
- `integration`: simulated transport/PTY/veth, deterministic and CI-safe;
- `hardware`: real USB adapters, opt-in/ignored by default;
- `soak`: long-running hardware test with report artifact.

Every hardware test records:

- Git commit and dependency pin;
- kernel, architecture, USB IDs/serials and driver;
- tty by-id paths, baud, latency setting and configuration;
- wiring, termination resistance and verified bias arrangement;
- counts, errors, latency/timing observations, start/end time and exit reason.

Never mark hardware behavior verified when adapters were unavailable. Compilation is not a hardware test.

## Agent workflow

1. Identify the smallest active-phase ticket.
2. Add or update a failing automated test where possible.
3. Implement without crossing phase boundaries.
4. Run formatting, Clippy, unit tests, and the relevant integration tests.
5. Provide the user exact hardware commands; do not mutate Ubuntu groups, udev, sysfs, network namespaces, or services automatically.
6. Record evidence in the phase results file.
7. Stop at the phase gate and request/await real bench evidence before advancing.

## Safety and repository hygiene

- Preserve the licensed BACnet PDF outside the repository. Cite clause numbers in prose; do not reproduce large portions.
- Never use default production credentials or clear-text stored passwords.
- Do not run normal data-plane services as root.
- Do not kill arbitrary UDP/serial owners. Diagnose and name the owner.
- No unbounded packet capture, support bundle, telemetry queue, or browser stream.
- Do not copy Contemporary Controls branding, UI assets, firmware, or trademarks. Functional comparison is allowed; product implementation must be original.
- Lab vendor identifiers and device instances must be visibly marked as non-production.

## Required commands before handoff

```bash
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
```

Run phase-specific integration/hardware commands as applicable and report each command's actual result.

