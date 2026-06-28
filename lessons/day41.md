## Day 41 – Intro rusty-bacnet & Clone the Stack

### Goal

Clone **[rusty-bacnet](https://github.com/jscott3201/rusty-bacnet)**, build examples, and locate **Who-Is / I-Am** and **ReadProperty** entry points in the crate docs.

### Concept

```bash
git clone https://github.com/jscott3201/rusty-bacnet.git
cd rusty-bacnet
cargo build
cargo test --no-run   # compile tests
```

Mental model:

- **BACnet/IP** = UDP `:47808`
- **BVLC** wraps network messages
- rusty-bacnet exposes Rust APIs instead of BACpypes3 objects

Map from Python days: `BAC0.read()` → rusty-bacnet read helpers (exact fn names vary by version—read `examples/`).

**Capstone path:** you'll wire this stack into [`capstone/discover-and-poll/`](./capstone/discover-and-poll/) for Day 46.

### Why This Matters

Open-FDD and edge gateways are moving to **Rust BACnet drivers** for memory safety and predictable latency on Pi-class hardware.

### Mini examples

- List files under `examples/` or `crates/` in your clone.
- Run one example against your lab device `5007 @ 192.168.204.200` if documented.

### Micro exercises

1. Document your `RUSTBACNET_*` or bind IP env vars if the stack needs them.
2. Compare Python Who-Is time vs Rust compile+run time (qualitative is fine).
3. Find where `47808` appears in source (`rg 47808`).

### Key takeaway

**rusty-bacnet is a specialty UDP client/server**—Days 36–39 networking labs are prerequisite, not optional.

### Wireshark Lab

Before running examples:

```bash
./capture_pcap.sh day41-rusty-whois "udp port 47808"
```

Filter: **`udp.port == 47808 && bacnet`**
