## Day 43 – ReadPropertyMultiple & Polling Loops

### Goal

Batch reads with **RPM**-style APIs and structure a **poll loop** suitable for edge historians.

### Concept

Python RPM lessons used CSV rotation—Rust pattern:

```rust
loop {
    // read multiple objects in one request
    // sleep(Duration::from_secs(60));
}
```

Use **`tokio::time::sleep`** if examples are async; **`thread::sleep`** for sync labs.

Design a `Vec<BacnetPoint>` from Day 32 and iterate.

### Why This Matters

Open-FDD **commission CSVs** become point lists—RPM reduces LAN chatter vs naive one-read-per-point Python loops.

### Mini examples

- Poll 3 points for 3 iterations; log timestamp with `chrono` if in examples.
- Stop loop on Ctrl+C (`ctrlc` crate optional).

### Micro exercises

1. Estimate BACnet traffic: 10 points × RPM vs 10 ReadProperty calls.
2. Store last values in `HashMap<String, f64>`.
3. Capture 60s pcap during poll—count UDP packets.

### Key takeaway

**Batch at the protocol level**—network programming *and* BACnet smarts.

### Wireshark Lab

```bash
PCAP_SECONDS=60 ./capture_pcap.sh day43-rpm "udp port 47808 and host 192.168.204.200"
```

Filter: **`udp.port == 47808`** — use **Statistics → IO Graph** for packet rate.
