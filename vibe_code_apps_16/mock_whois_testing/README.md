# mock_whois_testing — isolating the Open-FDD Who-Is discovery failure

Independent, minimal `rusty-bacnet` reproduction of the question:

> *"Is Open-FDD like VOLTTRON — where the BACnet proxy agent must be shut off
> before the auto-scan can build the registry, because they conflict on the
> socket if they run at the same time?"*

**Answer: yes, it is that class of problem — but the trigger is narrower and
worse.** Open-FDD does not run discovery *through* its local BACnet server
socket. It spins up a **separate discovery client on an ephemeral UDP port**
whenever the local server is enabled, and an ephemeral-port client **cannot
receive the broadcast `I-Am` replies** that Who-Is discovery depends on. So
discovery returns **zero devices every time**, regardless of the real network.

This crate proves that with a controlled A/B/C/D matrix against the live bench
(`192.168.204.55`, router `192.168.204.200`, MSTP device `5007` on net `2000`).

---

## Two implementations, same demo

The repo ships the identical experiment in **Rust** (`src/main.rs`, the
`mock_scan` binary) and **Python** (`python/mock_scan.py`, using the
[`rusty-bacnet` Python bindings](https://github.com/jscott3201/rusty-bacnet#quick-start-python)).
Both produce the same A/B/C/D result matrix below.

`mock_scan` sends a Who-Is and prints the devices it heard back from. The only
variables are:

- `--bind-port` — the discovery client's UDP port (`47808` vs `0`=ephemeral)
- `--with-local-server` — stand up a local `599999` BACnet server on `:47808`
  first (the Open-FDD "always-on local server" shape)

### Rust

```bash
cargo build
# A — working pattern (this is what rusty-bacnet's whois-scan sample does)
./target/debug/mock_scan --label A --bind-port 47808 --interface 192.168.204.55 --router-net 2000
# B2 — ephemeral client, nothing else running
./target/debug/mock_scan --label B2 --bind-port 0     --interface 192.168.204.55 --router-net 2000
# C  — Open-FDD shape: local server owns :47808, client forced to ephemeral
./target/debug/mock_scan --label C  --with-local-server --bind-port 0 --interface 192.168.204.55 --router-net 2000
# D  — proposed fix: client ALSO binds :47808 next to the server (SO_REUSEADDR)
./target/debug/mock_scan --label D  --with-local-server --bind-port 47808 --interface 192.168.204.55 --router-net 2000
```

### Python

```bash
cd python
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
python mock_scan.py --label A  --bind-port 47808 --interface 192.168.204.55
python mock_scan.py --label B2 --bind-port 0     --interface 192.168.204.55
python mock_scan.py --label C  --with-local-server --bind-port 0     --interface 192.168.204.55
python mock_scan.py --label D  --with-local-server --bind-port 47808 --interface 192.168.204.55
```

> The Python bindings have no `who_is_network`, but a plain global `who_is()`
> still reaches the routed MSTP device `5007` via the router — the Python matrix
> below confirms parity with Rust.

> Scenarios that bind `:47808` require the port to be free. On the bench that
> means the Open-FDD stack must be stopped first
> (`docker stop openfdd-bridge openfdd-commission openfdd-haystack-gateway`),
> which is itself the VOLTTRON "stop the proxy before you scan" lesson.

---

## Results (live bench, 2026-07-08, Open-FDD 3.2.13 @ 10c5aa5)

| # | Scenario | client port | local server on :47808 | Open-FDD analog | devices found | saw 5007? |
|---|----------|-------------|------------------------|-----------------|:-------------:|:---------:|
| **A** | working pattern (`whois-scan`) | **47808** | no | — (reference) | **5** | ✅ |
| **B** | ephemeral, real stack running | 0 (ephemeral) | yes (real commission+bridge) | **Open-FDD discovery today** | **0** | ❌ |
| **B2** | ephemeral, nothing else running | 0 (ephemeral) | no | isolate the port effect | **0** | ❌ |
| **C** | mock server + ephemeral client | 0 (ephemeral) | yes (mock 599999) | **Open-FDD shape, isolated** | **0** | ❌ |
| **D** | server + client both on 47808 | **47808** | yes (mock 599999) | **proposed fix** | **5** | ✅ |

Devices discovered in A and D:

```
device       0  addr 192.168.204.200:47808  net=28271   (router)
device    5007  addr 192.168.204.200:47808  net=2000    (MSTP field device — the target)
device   10001  addr 192.168.204.11:47808   net=None
device 3456789  addr 192.168.204.13:47808   net=None
device 3456790  addr 192.168.204.14:47808   net=None
```

**Python parity (same bench, `rusty-bacnet` bindings):** identical outcome —
PY-A and PY-D discovered all 5 devices incl. `5007`; PY-B2 and PY-C discovered
0. Both languages sit on the same Rust transport, so the socket behavior is the
same regardless of the API surface.

### What the matrix proves

1. **The ephemeral client port is the single root cause.** Binding `:47808`
   finds every device *with or without* a co-resident local server (A **and** D).
   Binding an ephemeral port finds **nothing** in every case (B, B2, C).
2. **It is not "the server steals the packet."** B2 has *no* server at all and
   still finds zero — an ephemeral socket is simply not listening on `:47808`,
   which is where broadcast `I-Am` is addressed.
3. **You do not have to stop the server to fix it.** Scenario D shows a client
   co-bound on `:47808` alongside the server hears broadcast `I-Am` fine, because
   the transport sets `SO_REUSEADDR` + `SO_BROADCAST` and Linux fans broadcast
   datagrams out to *all* sockets bound to that port.

---

## Why (the mechanism)

`bacnet-transport` binds `0.0.0.0:<port>` with `SO_REUSEADDR` and `SO_BROADCAST`
but **not** `SO_REUSEPORT`
(`rusty-bacnet/crates/bacnet-transport/src/bip/mod.rs:305-330`).

- A `rusty-bacnet` device (and a router forwarding a remote MSTP device like
  5007) answers Who-Is with a **broadcast** `I-Am` to `<subnet>.255:47808`.
- Linux delivers a broadcast datagram to **every** socket bound to that
  port/addr. A client on `:47808` is such a socket → it hears the `I-Am`.
  A client on an ephemeral port (e.g. `:52341`) is **not** bound to `:47808` →
  the datagram is never delivered to it.
- Unicast `ReadProperty` **acks**, by contrast, come back to the client's own
  source port, so **reads keep working on an ephemeral port** — which is exactly
  why the bench shows "reads work but discovery finds nothing."

`rusty-bacnet`'s own docs say the same thing:
- `whois-scan`: *"Binds UDP/47808 … required for rusty-bacnet devices that reply
  with broadcast I-Am"*; `--ephemeral` warns *"broadcast I-Am may not be received."*
- samples `README`: *"Only one process should bind UDP :47808 on a host at a time."*

---

## How this maps to Open-FDD (`open-fdd-src @ 10c5aa5`)

`edge/src/drivers/bacnet_live.rs:45-63` — `client_bind_port()` returns **0
(ephemeral)** whenever the local BACnet server is enabled, and the bench has
`OPENFDD_BACNET_SERVER_ENABLED=1`:

```rust
if server_on { 0 } else { 0xBAC0 }   // 0 == ephemeral → cannot hear broadcast I-Am
```

Every discovery entry point (`whois_devices`, `discover_device_points`,
`read_present_value` after a Who-Is) is built through `build_client()`, which
uses that ephemeral port. So on the bench they are all scenario **C/B** → 0
devices.

Worse, `edge/src/drivers/bacnet.rs:1156-1164` runs a **full-range** Who-Is every
30 s on *both* bridge and commission, via a client that can never hear the
answer — network Who-Is spam that is structurally guaranteed to fail.

See the full write-up:
`/home/ben/open-fdd/workspace/reports/BACNET_WHOIS_SOCKET_CONFLICT_ROOT_CAUSE.md`.
