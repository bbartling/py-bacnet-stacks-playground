# Architecture and Phase Separation

## End state

```text
BACnet/IP client network 100
          |
       UDP/BVLC
          |
  +-------------------------------+
  | bacnet-router appliance       |
  |                               |
  | B/IP Transport                |
  |       |                       |
  | NPDU Router + route table     |
  |       |                       |
  | MS/TP Transport, MAC 0        |
  |                               |
  | Read-only telemetry API       |
  | Commissioning web app         |
  +-------------------------------+
          |
  Waveshare C adapter A
          |
  A+ / B- / field reference
          |
  Waveshare C adapter B
          |
  Phase 2 MS/TP mini-device, MAC 1
  BACnet device instance 123001
```

The two adapters remain physical endpoints on the first bench segment. The final field product needs switchable termination and bias because a router is not guaranteed to be installed at a segment endpoint.

## Shared code boundaries

```text
crates/lab-common
  baud policy
  serial/MS/TP configuration validation
  report schemas and bounded telemetry types (added by Phase 1)

apps/serial-wire-test
  raw byte path only
  no BACnet dependencies

apps/mstp-mini-device
  object database + BACnet services
  MstpTransport only
  no IP/web dependencies

apps/bacnet-router
  B/IP + MS/TP transports
  NPDU routing only on the data plane
  management API/UI outside timing loop
```

Phase 2 may reuse Phase 1 serial identity/report helpers. Phase 3 may reuse Phase 1 serial helpers and MS/TP test fixtures, but it must not reuse the Phase 2 application object database.

## Process model

### Phase 1

One process owns both ttys and alternates raw transmissions. This is intentionally unlike MS/TP; it proves the physical and USB path before protocol timing is involved.

### Phase 2

Two processes own one tty each:

- `mstp-probe` on adapter A, MAC 0;
- `mstp-mini-device` on adapter B, MAC 1.

Both are MS/TP masters so the test exercises token discovery, sole-master behavior, token passing, request/reply and restart admission.

### Phase 3

- `bacnet-router` owns adapter A, MAC 0 and B/IP network 100;
- `mstp-mini-device` owns adapter B, MAC 1;
- `bip-probe` runs inside Linux network namespace `baclab` on `10.77.0.2/24`;
- the router binds host-side `10.77.0.1/24` and routes to MS/TP network 2001.

The namespace gives the B/IP client a separate network stack without requiring a second computer.

## Rust stack integration

The reviewed `rusty-bacnet` `dev` snapshot contains:

- `MstpTransport<S: SerialPort>` and `TokioSerialPort`;
- hardware automatic direction suitable for the Waveshare adapters;
- `AnyTransport<S>` for mixed B/IP + MS/TP router ports;
- `BACnetRouter` with directly connected/learned route handling;
- server/object/service code used by the upstream mini-device example.

Before Phase 2, inspect whether the pinned `BACnetServer` can be constructed with a generic `MstpTransport`. The sample currently calls a B/IP-specific builder. If a generic server entry point does not exist, add the smallest transport-generic server constructor upstream/local rather than copying the APDU dispatcher or reimplementing MS/TP.

## Data-plane isolation

The following must never block the MS/TP receive/token task:

- disk writes;
- JSON serialization;
- console or structured logging;
- HTTP request/response;
- browser polling, SSE or WebSocket clients;
- configuration persistence;
- packet capture;
- support bundles;
- MCP or other automation.

Use bounded queues. Dropped noncritical telemetry increments a visible counter. Control/config changes are validated outside the data plane and applied through explicit lifecycle operations.

## Router versus device

The Phase 2 mini-device is an application endpoint. It has a Device object and four points and consumes BACnet services addressed to MAC 1.

The Phase 3 router forwards NPDUs between network 100 and network 2001. Its MS/TP MAC 0 is a link-layer router address. It must not answer for the Phase 2 points or masquerade as that application device. Router Device/Network Port objects, if added for a PICS, are a separate feature with separate object instances and tests.

## Configuration ownership

- CLI arguments override configuration files only when explicitly supplied.
- All serial-facing surfaces share the same six-value `BaudRate` type.
- Runtime config is versioned and validated before opening ports.
- Writes use temporary file + fsync as appropriate + atomic rename.
- An invalid update leaves the last known-good config active.
- Settings that change transport require an explicit apply/restart operation.

## Security boundary

Initial web deployment binds `127.0.0.1:8080`; Caddy/Nginx supplies HTTPS and Basic authentication. Normal router operation is unprivileged. The service account receives only the chosen serial device and necessary network access. Phase 3 does not expose clear-text Basic Auth on a production LAN.

