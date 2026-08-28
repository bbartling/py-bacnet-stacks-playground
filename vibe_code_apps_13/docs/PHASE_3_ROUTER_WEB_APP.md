# Phase 3 - BACnet/IP-to-MS/TP Router and Web Appliance

## Objective

Build an original BASRT-B-class Linux appliance that forwards NPDUs between BACnet/IP network 100 and MS/TP network 2001, then provides a small authenticated commissioning and diagnostics web application.

The router is not the Phase 2 mini-device. Its MS/TP MAC 0 is a routing port; Phase 2 remains the downstream application device at MAC 1.

## Same-PC routed topology

```text
Linux namespace baclab
bip-probe 10.77.0.2:47808
BACnet network 100
        |
      veth
        |
bacnet-router 10.77.0.1:47808
        |
AnyTransport: BIP + Mstp
        |
MS/TP network 2001, router MAC 0
        |
mstp-mini-device MAC 1, instance 123001
```

The namespace and veth scripts are privileged setup tools. The router process itself should remain unprivileged.

## Current Rust integration

Use the pinned source's `AnyTransport<S>` with:

```text
AnyTransport::Bip(BipTransport)
AnyTransport::Mstp(MstpTransport<TokioSerialPort>)
```

Pass two `RouterPort<AnyTransport<_>>` entries to `BACnetRouter::start`. Reinspect exact generic inference and feature flags at the pinned commit.

The current router calls itself a half-router. Treat its unit tests as a starting point, not a product/conformance result. Add hardware evidence for both directions and every network control message claimed.

## Extended-frame prerequisite

ANSI/ASHRAE 135-2020 requires routing nodes to support COBS-encoded extended MS/TP frames. Before a conformance claim:

- implement frame types 32/33;
- implement COBS and CRC-32K;
- separate standard/extended limits;
- use independent known-answer vectors;
- test actual extended traffic against current `bacnet-stack` or another implementation;
- fuzz malformed/truncated data;
- ensure router buffers support the maximum claimed NPDU plus encoding overhead.

An early standard-frame prototype is allowed only when clearly labeled and hard-capped. Never send a payload larger than the standard limit under frame type 5 or 6.

## Router acceptance sequence

`bip-probe` inside `baclab` must:

1. send Who-Is-Router-To-Network for 2001;
2. verify I-Am-Router-To-Network;
3. route Who-Is for instance 123001;
4. receive routed I-Am from MS/TP MAC 1;
5. repeat Phase 2 RP/RPM/WP/relinquish/negative tests;
6. test local, remote and global broadcasts without ingress reflection or loop;
7. test hop-count decrement/exhaustion;
8. test unknown DNET rejection;
9. test nonexistent destination MAC timeout;
10. complete 1,000 routed reads with correlated B/IP capture, MS/TP trace and counters.

## Management API and UI order

Do not build the write/config UI before routing passes.

### 1. Structured telemetry

- uptime, version and dependency commit;
- port state/config and last error;
- bytes/frames/NPDUs in/out per port;
- directly connected and learned routes;
- unicast/broadcast/forward/discard counters;
- MS/TP state, observed masters, token/lost-token recovery;
- header/data/COBS/CRC errors and timeouts;
- bounded recent events and telemetry-drop count.

### 2. Read-only local API

Serve bounded JSON snapshots without locks or backpressure on the data plane.

### 3. Tiny status UI

- overall B/IP and MS/TP health;
- network 100 <-> 2001 route;
- MS/TP master map and last seen;
- traffic/error totals;
- bounded event log.

### 4. Commissioning writes

- device/router identity as appropriate;
- B/IP interface, port and network;
- MS/TP serial, network, MAC, baud, Max_Master, Max_Info_Frames;
- validate/dry-run/apply/rollback;
- audit log and CSRF protection.

### 5. Later product features

- BBMD/BDT/FDT and foreign-device registration;
- second B/IP port/NAT requirements;
- support bundle and bounded packet capture;
- signed updates and rollback;
- PICS/BTL work.

## Web security baseline

- bind application HTTP to loopback by default;
- put HTTPS and Basic Auth at Caddy/Nginx initially;
- no factory default password;
- no clear-text credential storage;
- mutation CSRF protection, rate limits and audit events;
- unprivileged service account with access only to selected tty;
- web/API failure cannot stop forwarding.

## Fault and soak matrix

- restart router while downstream device remains up;
- restart device while router remains up;
- unplug/replug router adapter;
- veth down/up;
- B/IP client stop/restart;
- malformed NPDU and unknown DNET;
- CPU/disk/log/browser load;
- standard and genuine extended frame interop;
- 8-hour development gate then 48-72-hour release soak.

## Exit checklist

- [ ] Phases 1 and 2 remain green.
- [ ] `AnyTransport` integration has delegation/forwarding tests.
- [ ] Route discovery and routed application acceptance pass.
- [ ] Hop count, rejection and broadcast behavior pass.
- [ ] Extended frames pass independent vectors and real interop.
- [ ] 1,000 routed reads have no unexplained mismatch.
- [ ] Router does not expose Phase 2 points.
- [ ] Data plane survives web/API failure and telemetry backpressure.
- [ ] 8-hour and then 48-hour soak evidence retained.
- [ ] Product claims remain limited to implemented/tested PICS behavior.

