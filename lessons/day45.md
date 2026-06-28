## Day 45 – Who-Is / I-Am Device Discovery Scan

### Goal

Build or run a **discovery scan** listing device IDs and addresses—Rust replacement for Python Who-Is apps.

### Concept

Discovery flow:

1. Send **Who-Is** (global or range)
2. Collect **I-Am** responses into `HashMap<u32, SocketAddr>`
3. Print table sorted by device id

```rust
// for (id, addr) in devices.iter() {
//     println!("{id} @ {addr}");
// }
```

### Why This Matters

Commissioning starts with **what's on the wire**—same as vibe_code_apps discovery checkpoints.

### Mini examples

- Limit scan to device range `5000-5010`.
- Compare scan results to your known `5007` bench device.

### Micro exercises

1. Run scan while capturing pcap—count I-Am packets.
2. Export device list to CSV from Rust (`writeln!` is enough).
3. Merge duplicate I-Ams—why might you see two?

### Key takeaway

**Discovery is UDP broadcast/multicast behavior**—routing issues show up here first.

### Wireshark Lab

Filter: **`bacnet && bacnet.bvlc.function == 0x0b`** (Who-Is / I-Am family—verify field names in your Wireshark build).
