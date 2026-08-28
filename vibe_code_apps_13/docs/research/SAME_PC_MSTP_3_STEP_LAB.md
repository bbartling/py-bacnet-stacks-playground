# Same-PC BACnet MS/TP Lab: Wire Test → Rust Device → Router

Implementation brief for an Ubuntu x86 tower with two Waveshare USB-to-RS-485 adapters.

This is intentionally written as an engineering handoff: detailed enough for a coding agent to implement, but still organized as three independently provable milestones rather than one large prompt.

## Adapter choice

Use the two **Waveshare USB TO RS485 (C)** adapters for the first baseline and the eventual router/device pair. The C model uses FT232RNL, is explicitly optically isolated to 2.5 kV, and exposes the familiar FTDI Linux driver and latency controls. The B model uses CH343G/SP485EEN, has a higher headline baud ceiling but is not specified as isolated, and may enumerate through Linux CDC-ACM as `ttyACM*`. That extra speed is not useful for the intended MS/TP rates.

Keep the two B adapters: after C+C passes, B+B is a valuable portability test for the serial code, and B+C is a useful final cross-chip interoperability check. Do not begin with mixed models because an asymmetric failure is harder to diagnose. Both product pages specify an onboard 120-ohm resistor, so treat each adapter as an endpoint unless measurement or hardware inspection proves the termination can be disabled.

## Short answer

Two adapters plugged into the same PC and wired to the same two-wire bus are a valid MS/TP test bench. It is not merely a software loopback:

- each adapter has its own USB endpoint, UART, RS-485 transceiver, buffering, and direction control;
- bytes physically leave one transceiver and enter the other over A/B;
- two independent Linux processes can behave as separate MS/TP stations;
- the real MS/TP token state machine, timing, CRC, broadcasts, requests, and replies are exercised.

The shared CPU and kernel make it less independent than using an x86 plus Raspberry Pi, and a short bench cable does not reproduce a long noisy trunk. Those are later validation steps, not reasons to skip this very useful first rig.

## Final one-machine topology

```text
Ubuntu x86 tower

  Linux network namespace "baclab"
  10.77.0.2/24
  Rust BACnet/IP test client
             |
          veth pair
             |
  host 10.77.0.1/24
  Rust BACnet/IP ↔ MS/TP router
             |
  Adapter A: router, MS/TP MAC 0
             |
       A+ ========= A+
       B- ========= B-
       REF ======== REF       one short RS-485 trunk
             |
  Adapter B: Rust device, MS/TP MAC 1
  Device instance 123001
```

The three milestones reuse the same hardware:

| Milestone | Adapter A | Adapter B | IP side |
|---|---|---|---|
| 1. Wire test | Raw serial endpoint A | Raw serial endpoint B | None |
| 2. MS/TP device | Rust MS/TP tester, MAC 0 | Rust MS/TP device, MAC 1 | None |
| 3. Router | Rust router MS/TP port, MAC 0 | Rust MS/TP device, MAC 1 | Rust B/IP client in namespace |

Never allow two processes to open the same serial device simultaneously.

## Bench preparation

### Electrical setup

1. Disconnect both adapters before changing wiring.
2. Connect adapter A+ to adapter A+, and B- to B-. Use the labels on the actual model rather than wire color.
3. Connect the RS-485 reference/ground terminals as recommended by the specific adapter manual. The reference is not an excuse to connect protective earth or bypass galvanic isolation.
4. Keep the first cable short and daisy-chained. Do not create a star.
5. Terminate only the two physical ends. If both Waveshare units contain 120-ohm termination, they are the two ends and may already provide both terminators.
6. With equipment powered off, measure resistance across A/B. Two effective 120-ohm terminators in parallel should measure approximately 60 ohms. If the result is closer to 40 ohms, a third termination is present; around 120 ohms normally means only one end is terminated.
7. Confirm that the selected adapters provide automatic transmit direction. For the Waveshare FTDI auto-direction model, use the Rust serial transport's `Auto` mode; do not also enable Linux `TIOCSRS485` or GPIO RTS direction.
8. Begin at 38,400 baud, 8 data bits, no parity, one stop bit, and no flow control.

For a short two-node bench, termination problems can sometimes be masked by generous signal margins. Record the resistance and adapter model instead of assuming that successful traffic proves correct termination.

### Stable Linux device identity

Use `/dev/serial/by-id` paths, not `/dev/ttyUSB0` and `/dev/ttyUSB1`. Linux may reverse tty numbers after a reboot or unplug.

```bash
ls -l /dev/serial/by-id/
lsusb
udevadm info --query=all --name=/dev/ttyUSB0
udevadm info --query=all --name=/dev/ttyUSB1
```

Label the physical adapters “A” and “B” and record:

- manufacturer/model;
- USB vendor/product IDs;
- USB serial number;
- `/dev/serial/by-id/...` path;
- whether termination is fitted or switchable;
- the Linux tty currently assigned.

If two adapters expose identical or missing serial numbers, create udev aliases based on their physical USB port paths and keep them in those ports. Serial-number aliases are preferable because they survive USB-port movement.

### Permissions and USB latency

The applications should run as the normal user, typically through membership in Ubuntu's `dialout` group:

```bash
sudo usermod -aG dialout "$USER"
```

Log out and back in after changing group membership. Verify access rather than running the application as root.

FTDI USB serial drivers commonly expose a `latency_timer`. Inspect both ttys:

```bash
cat /sys/bus/usb-serial/devices/ttyUSB0/latency_timer
cat /sys/bus/usb-serial/devices/ttyUSB1/latency_timer
```

If the nodes exist, benchmark a value of 1 ms for the lab. The eventual udev rule should target only the known adapters. Do not assume the sysfs path on every kernel or adapter family.

If a port is unexpectedly busy, identify the owner with `lsof`/`fuser`. ModemManager should only be disabled or given an `ID_MM_DEVICE_IGNORE` udev rule if logs prove that it is probing these exact adapters.

## Suggested source layout

Create one Cargo workspace so all three milestones share serial configuration, logging, and test fixtures:

```text
bacnet-router-lab/
  Cargo.toml
  Cargo.lock
  README.md
  crates/
    lab-common/
      src/
        config.rs
        serial.rs
        telemetry.rs
    serial-wire-test/
      src/main.rs
    mstp-device/
      src/main.rs
    mstp-client/
      src/main.rs
    bacnet-router/
      src/main.rs
    bip-client/
      src/main.rs
  config/
    wire-test.toml
    mstp-device.toml
    mstp-client.toml
    router.toml
    bip-client.toml
  scripts/
    show-adapters.sh
    setup-baclab-netns.sh
    teardown-baclab-netns.sh
  captures/
    .gitkeep
  docs/
    bench-inventory.md
    test-results.md
```

Pin an exact `rusty-bacnet` release or audited Git revision and commit `Cargo.lock`. The current research baseline is release `0.10.1`. Enable its Linux serial feature. A coding agent must inspect the actual pinned APIs and examples before writing code; it must not invent API calls from this document.

Do not add the Coleman kernel line discipline or `rusty-bacnet-mcp` to these three milestones. They solve different problems and would make failures harder to localize.

# Milestone 1 — prove the adapters and physical wire

## Goal

Demonstrate reliable bytes in both directions over the actual RS-485 transceivers before any BACnet framing or token logic is introduced.

## Deliverable

Implement `serial-wire-test`, a single Rust process that opens both adapters and performs controlled half-duplex exchanges.

Command shape:

```bash
cargo run -p serial-wire-test -- \
  --port-a /dev/serial/by-id/ADAPTER_A \
  --port-b /dev/serial/by-id/ADAPTER_B \
  --baud 38400 \
  --rounds 10000 \
  --max-payload 256 \
  --report captures/wire-test.json
```

## Wire-test protocol

This is a private lab envelope, not BACnet:

```text
Preamble       2 bytes   0x55 0xAA
Direction      1 byte    A→B or B→A
Sequence       4 bytes   monotonically increasing, big endian
Payload length 2 bytes   big endian
Payload        N bytes
CRC-32         4 bytes   over direction through payload
```

Required behavior:

1. Open both ttys with identical baud/8N1/no-flow-control settings.
2. Drain stale bytes for a bounded time and report anything found.
3. Send one complete envelope from A and read/validate it on B.
4. Wait until transmission and direction turnaround are complete, then send the next envelope from B to A.
5. Alternate directions. Do not write both ports simultaneously during the baseline.
6. Test fixed patterns `00`, `FF`, `55`, `AA`, an incrementing byte ramp, and deterministic pseudorandom payloads.
7. Sweep payload lengths around meaningful boundaries: 0, 1, 2, 7, 8, 15, 16, 63, 64, 127, 128, 255, and 256 bytes.
8. Bound every read with a timeout. A timeout is a failed frame, not a reason to hang the test.
9. Detect and report local echo on the transmitting adapter separately from the intended peer reception. If the hardware echoes, drain/validate it without counting it as the peer result.
10. Record direction, sequence, byte counts, missing/corrupt/duplicate frames, latency histogram, tty errors, start/end timestamps, adapter paths, and baud.
11. Exit nonzero on any missing or corrupt frame.

Use deterministic random seeds so a failed sequence can be reproduced. Keep the serial reader incremental: USB may split one envelope across arbitrary read boundaries or return several envelopes in one read.

## Milestone 1 tests

Run in this order:

1. 100 exchanges at 38,400 baud while watching logs.
2. 10,000 alternating exchanges at 38,400 baud.
3. Repeat at 9,600 and 76,800 baud if both adapters claim those rates.
4. Unplug adapter B during a short run; the program must fail clearly without spinning or hanging.
5. Replug B and repeat using the stable by-id path.
6. Run with ordinary CPU load to expose excessive USB scheduling sensitivity.

An optional later test may deliberately transmit simultaneously to demonstrate collision/corruption detection. It is not part of the baseline and must never be confused with valid MS/TP arbitration.

## Milestone 1 exit gate

- zero missing, duplicate, or corrupt envelopes in the 10,000-frame baseline at 38,400 baud;
- bidirectional data confirmed through the physical transceivers;
- stable adapter identity documented;
- unplug produces a bounded, understandable error;
- report file committed or attached to the test record.

Do not proceed to debugging BACnet if this gate fails.

# Milestone 2 — make a real two-master Rust MS/TP network

## Goal

Run a small BACnet MS/TP device on adapter B and a BACnet MS/TP test client on adapter A. This proves Rust framing, CRC, timing, token passing, application services, and recovery without routing.

## Station assignments

| Setting | Tester on adapter A | Device on adapter B |
|---|---:|---:|
| MS/TP MAC | 0 | 1 |
| Max_Master | 3 | 3 |
| Max_Info_Frames | 1 | 1 |
| Baud | 38,400 | 38,400 |
| Direction mode | Auto | Auto |
| MS/TP network | local/direct | local/direct |

Both stations should initially be masters. A slave-only device is a poor first test because it does not exercise normal token participation and makes unconfirmed I-Am behavior less representative.

Keep the standard-frame APDU limit at 480 for this milestone. Do not claim or exercise MS/TP extended frames until the Rust extended-frame path has independent golden tests.

## `mstp-device` requirements

The device process owns adapter B exclusively and presents device instance `123001`. Make the instance and all identity fields configurable.

Minimum object model:

| Object | Instance | Purpose |
|---|---:|---|
| Device | 123001 | Identity, object list, protocol and MS/TP properties |
| Analog Input | 0 | Read-only simulated temperature |
| Analog Value | 1 | Writable setpoint with priority array |
| Binary Value | 2 | Writable enable command |

Suggested lab values:

- Device Object_Name: `Rust MS/TP Bench Device`;
- model: `rusty-bacnet-lab`;
- Analog Input 0 Object_Name: `Simulated Temperature`;
- temperature changes deterministically and slowly between sensible values;
- Analog Value 1 defaults to `72.0` and supports relinquishing a commanded priority;
- Binary Value 2 defaults inactive;
- segmentation reports unsupported for the first milestone;
- vendor identifier is configuration, with a clearly marked lab-only placeholder that must not ship in a product.

Minimum services:

- Who-Is → I-Am;
- ReadProperty;
- ReadPropertyMultiple;
- WriteProperty for writable AV/BV Present_Value;
- appropriate BACnet Error/Reject/Abort behavior for unknown objects, unknown properties, invalid data types, denied writes, and unsupported services.

The agent should first locate the pinned stack's server/device examples and reusable object database. If the library lacks a complete server runner, implement the smallest application dispatcher around its transport/network/APDU codecs; do not create a second MS/TP state machine.

Runtime behavior:

- log device instance, MAC, tty, baud, Max_Master, and Max_Info_Frames at startup;
- expose current MS/TP state and counters through structured logs;
- handle SIGINT/SIGTERM and release the tty cleanly;
- reject a second process opening the port;
- never let simulated-value updates block serial receive/token processing.

## `mstp-client` requirements

The client owns adapter A exclusively. It needs interactive subcommands and a scripted acceptance mode:

```bash
cargo run -p mstp-client -- --config config/mstp-client.toml discover
cargo run -p mstp-client -- --config config/mstp-client.toml read 123001 device:123001 object-name
cargo run -p mstp-client -- --config config/mstp-client.toml acceptance
```

The scripted acceptance sequence should:

1. wait for the two-master token ring to stabilize;
2. broadcast Who-Is and find instance 123001 via I-Am;
3. ReadProperty Device Object_Name;
4. ReadProperty Device Object_List;
5. ReadProperty Analog Input 0 Present_Value;
6. use ReadPropertyMultiple for several device and analog properties;
7. WriteProperty Analog Value 1 Present_Value to `75.0` at priority 8;
8. read it back and verify `75.0`;
9. relinquish priority 8 with BACnet NULL and verify the relinquish/default result;
10. write/read Binary Value 2;
11. request a nonexistent object and verify a proper error response;
12. request a write to the Analog Input and verify write-access denial;
13. perform at least 500 repeated reads while tracking timeouts and response latency.

Every transaction should print invoke ID, destination MAC, service, result, elapsed time, retry count, and decoded error when relevant.

## Milestone 2 observation and fault tests

- start device first, then client;
- reverse the startup order;
- stop/restart the client while the device remains a sole master;
- stop/restart the device while the client remains a sole master;
- give both processes the same MAC and confirm the logs/counters make the fault visible;
- mismatch the baud and confirm there are no false successful transactions;
- unplug/replug one adapter and verify the failure/recovery policy;
- run for one hour with one read per second;
- run under CPU and logging load;
- save Rust trace logs and a logic-analyzer capture if available.

Do not attach a third Waveshare as a passive sniffer if its fixed termination would create a third 120-ohm load. A third receiver is useful only when it can be placed in receive-only mode without disturbing termination/bias. A logic analyzer or isolated high-impedance RS-485 capture interface is safer.

## Milestone 2 exit gate

- both masters visibly participate in token passing;
- discovery, RP, RPM, WP, relinquish, and negative cases behave correctly;
- 500 repeated reads complete without unexplained timeout or corrupted response;
- either process can become sole master and admit the returning master;
- the one-hour run has no deadlock, runaway CPU, memory growth, or silent task death;
- extended frames remain explicitly disabled/limited unless independently fixed and tested.

# Milestone 3 — route BACnet/IP to the Rust MS/TP device

## Goal

Replace the MS/TP tester on adapter A with the router. Put a BACnet/IP test client in a Linux network namespace so the entire routed request path exists on one tower while using a genuinely separate IP network stack.

## Virtual BACnet/IP LAN

Use a named namespace and veth pair:

| Endpoint | Address | Role |
|---|---|---|
| Host `veth-router` | `10.77.0.1/24` | Router B/IP port, BACnet network 100 |
| Namespace `veth-client` | `10.77.0.2/24` | B/IP test client |
| Subnet broadcast | `10.77.0.255` | Local B/IP broadcast |
| UDP port | `47808` (`0xBAC0`) | Both network namespaces may bind it |
| MS/TP network | `2001` | Router adapter A and device adapter B |

The setup script should be idempotent: inspect existing links/namespace, refuse to overwrite unrelated objects, and create only the exact names it owns.

Conceptual setup commands:

```bash
sudo ip netns add baclab
sudo ip link add veth-router type veth peer name veth-client
sudo ip link set veth-client netns baclab
sudo ip address add 10.77.0.1/24 dev veth-router
sudo ip link set veth-router up
sudo ip netns exec baclab ip address add 10.77.0.2/24 dev veth-client
sudo ip netns exec baclab ip link set lo up
sudo ip netns exec baclab ip link set veth-client up
```

The teardown script must delete only the specifically named `baclab` namespace and `veth-router` interface after verifying their identities. The namespace can access the same executable and configuration files on the host filesystem.

Use `tcpdump` or Wireshark on both `veth-router` and `veth-client` to capture B/IP. Keep serial/MS/TP tracing inside the Rust transport or on a suitable external analyzer.

## Router configuration

Illustrative configuration:

```toml
[device]
name = "rust-bacnet-router-lab"
instance = 123000

[bip]
bind = "10.77.0.1:47808"
broadcast = "10.77.0.255:47808"
network = 100

[mstp]
device = "/dev/serial/by-id/ADAPTER_A"
network = 2001
mac = 0
baud = 38400
max_master = 3
max_info_frames = 1
direction = "auto"
max_apdu = 480

[telemetry]
log = "info"
route_snapshot_seconds = 5
```

Network 100 and network 2001 must be different. The router's MS/TP MAC 0 and device MAC 1 must be unique.

## Heterogeneous router implementation

The current generic Rust router expects all ports in its vector to use one concrete transport type. Add an appliance-local enum rather than rewriting the router core initially:

```rust
enum AppliancePort {
    Bip(BipTransport),
    Mstp(MstpTransport<TokioSerialPort>),
}
```

Implement the pinned version's complete `TransportPort` trait by delegating each method to the active variant. Then construct:

```text
RouterPort<AppliancePort> for B/IP network 100
RouterPort<AppliancePort> for MS/TP network 2001
```

Add unit/integration tests for enum delegation before hardware testing. Test both directions; compiling the enum does not prove correct source/destination address conversion, broadcasts, maximum NPDU sizing, shutdown, or error propagation.

The router process owns adapter A. `mstp-device` continues owning adapter B. `mstp-client` must be stopped.

## `bip-client` requirements

Run the client inside the namespace:

```bash
sudo ip netns exec baclab \
  target/debug/bip-client --config config/bip-client.toml acceptance
```

It should bind `10.77.0.2:47808` and use B/IP network 100. It needs to construct routed NPDUs for destination network 2001 and destination MS/TP MAC 1.

Acceptance sequence:

1. send Who-Is-Router-To-Network for network 2001;
2. verify I-Am-Router-To-Network reports 2001 through the B/IP port;
3. send a routed Who-Is for device instance 123001;
4. receive the routed I-Am from MS/TP MAC 1;
5. repeat the Milestone 2 RP, RPM, WP, relinquish, and negative object/property tests through the router;
6. send a directed request to nonexistent MS/TP MAC 2 and verify a bounded timeout rather than a router deadlock;
7. send toward an unreachable DNET and verify the appropriate network-layer rejection when required;
8. test remote and global broadcasts and verify that the router does not reflect a broadcast back to its ingress port;
9. verify hop count is decremented and packets at the terminal hop condition are not forwarded;
10. perform 500–1,000 routed reads while recording end-to-end latency and router counters.

Capture packets on the veth interface and correlate B/IP invoke IDs with MS/TP frames and router logs.

## Router telemetry required before a web UI

Expose these first as structured logs and a read-only local JSON endpoint:

- uptime and version/commit;
- port state and last error;
- frames, NPDUs, and bytes in/out per port;
- directly connected and learned network table;
- forwarded unicast, broadcast, and discarded packet counts;
- malformed NPDU, bad route, hop-count, timeout, and queue-overflow counts;
- MS/TP token state, observed masters, CRC/header errors, retries, token recovery, and last activity;
- current config with secrets and sensitive paths redacted as appropriate.

Only after routed traffic passes should the small HTML page be added. The first page can poll the read-only endpoint and show:

- green/yellow/red B/IP and MS/TP status;
- network 100 ↔ network 2001 route;
- observed MS/TP MAC 1 and last-seen time;
- traffic/error counters;
- bounded recent events.

Configuration writes, authentication, BBMD/FDR, updates, and polished UI are follow-on work. They must not be allowed to obscure a data-plane fault in this milestone.

## Milestone 3 fault tests

- restart only the router while the MS/TP device stays up;
- restart only the device while the router stays up;
- unplug/replug adapter A;
- bring the veth interface down/up;
- stop the B/IP client midway through traffic;
- send malformed/unknown DNET NPDUs from a controlled test case;
- create heavy localhost CPU and disk/log load;
- run routed reads for 8 hours, then 48 hours;
- confirm route and error counters explain every injected fault.

## Milestone 3 exit gate

- route discovery identifies network 2001;
- Who-Is/I-Am, RP, RPM, WP, relinquish, and negative cases work through B/IP → MS/TP → B/IP;
- no broadcast loop or ingress reflection;
- hop-count and unreachable-network behavior are correct;
- restart/unplug failures are bounded, visible, and recover according to policy;
- 1,000 routed reads have no unexplained response mismatch;
- an 8-hour soak passes before dashboard/configuration work proceeds.

## Coding-agent work tickets

These tickets are deliberately small enough to review individually:

1. **LAB-001 — repository and pinned dependencies:** create workspace, pin `rusty-bacnet`, add formatting/lint/test CI, and document exact commit/toolchain.
2. **LAB-002 — adapter inventory/config:** common typed serial config, by-id validation, startup diagnostics, and exclusive-open errors.
3. **LAB-003 — raw wire tester:** alternating framed exchanges, incremental parser, CRC, timeouts, JSON report, and automated parser tests.
4. **LAB-004 — MS/TP device skeleton:** open adapter B, join as MAC 1, clean lifecycle, structured token/frame logs.
5. **LAB-005 — object database/services:** Device, AI, AV, BV plus Who-Is/I-Am, RP, RPM, WP, and proper negative responses.
6. **LAB-006 — MS/TP scripted client:** discovery, read/write/relinquish/negative acceptance suite and latency report.
7. **LAB-007 — Milestone 2 hardware runbook:** startup permutations, duplicate MAC, baud mismatch, unplug, load, and one-hour soak.
8. **LAB-008 — network namespace scripts:** safe/idempotent setup, status, packet-capture hints, and narrowly scoped teardown.
9. **LAB-009 — heterogeneous transport enum:** delegation tests for every transport trait operation.
10. **LAB-010 — router binary:** B/IP network 100 plus MS/TP network 2001, routing messages, graceful shutdown, and telemetry.
11. **LAB-011 — B/IP scripted client:** route discovery and the full routed application acceptance suite.
12. **LAB-012 — router fault/soak suite:** counters, captures, 8-hour gate, and results document.
13. **LAB-013 — read-only status UI:** only after LAB-012 passes.

Each ticket should add or update tests and the runbook. Do not accept a ticket based only on successful compilation.

## Guardrails for the implementation agent

- Inspect the exact pinned `rusty-bacnet` source and examples before coding against its APIs.
- Keep one owner per tty and give every async task a bounded shutdown path.
- Never block the MS/TP receive/token task on logging, JSON, disk, web, or a slow consumer.
- Use bounded queues and increment an explicit drop counter if a noncritical telemetry event is lost.
- Do not silently truncate APDUs or pretend extended MS/TP works.
- Keep application/service timeouts separate from raw serial read timing.
- Use deterministic tests and retain failing seeds/captures.
- Do not require root for normal serial or router operation; namespace setup is the separate privileged step.
- Do not add the web dashboard until the router data plane passes its gate.
- Do not add the kernel line discipline, MCP, BBMD, FDR, containers, or firmware updating to these three milestones.
- Preserve captured evidence: configs, exact binary commit, kernel version, adapter IDs, latency setting, logs, and pass/fail report.

## Cool follow-on experiments once the three gates pass

1. **Move the device to the Raspberry Pi:** run the identical `mstp-device` binary/config on ARM to separate the scheduler, USB controller, and power domain.
2. **Passive bus map/sniffer:** use a high-impedance receive-only interface to display tokens, Poll-For-Master, masters, frame types, CRC errors, and utilization in the dashboard.
3. **Fault injector:** a carefully configured third interface can inject noise, truncated headers, bad CRCs, duplicate MAC traffic, or a stuck talker. It must not add unwanted termination and should be used only on the isolated bench.
4. **Multiple MS/TP trunks:** with four adapters, run two independent two-wire segments and route B/IP network 100 to MS/TP networks 2001 and 2002. This is an excellent test of the heterogeneous-port abstraction and routing table.
5. **IP impairment:** use `tc netem` only on the named veth interface to add B/IP delay, loss, duplication, and reordering while verifying the MS/TP token task remains healthy.
6. **USB recovery test:** where the tower's hub supports it, use controlled per-port power cycling to verify stable by-id recovery and serial reopen policy.
7. **Animated bus dashboard:** show the current token owner, observed masters, request/reply path, CRC/error counters, and B/IP-to-MS/TP forwarding in real time.
8. **Differential oracle:** run the current C `bacnet-stack` device/router against the same Rust endpoints and compare wire captures and service behavior.

The same-PC rig is ideal for automated development. Passing it is necessary, but final confidence still requires the Pi, several real vendor devices, long cable/noise conditions, different USB chipsets, and a current C stack or commercial router as an independent reference.

## Definition of the first useful prototype

The first prototype is complete when one command starts the MS/TP device on adapter B, one starts the router on adapter A, one creates the isolated B/IP namespace, and the B/IP acceptance client can discover, read, write, relinquish, and repeatedly poll device 123001 through the full routed path—with captures and counters proving where every packet went.
