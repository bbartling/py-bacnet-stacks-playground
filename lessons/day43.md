# Day 43 – ReadPropertyMultiple & Polling Loops

## Goal

Batch reads with **RPM**-style APIs and structure a **poll loop** suitable for edge historians.

## Concept

Python RPM lessons used CSV rotation—Rust pattern:

```rust
loop {
    // read multiple objects in one request
    // sleep(Duration::from_secs(60));
}
```

Use **`tokio::time::sleep`** if examples are async; **`thread::sleep`** for sync labs.

Design a `Vec<BacnetPoint>` from Day 32 and iterate.

## Why This Matters

Open-FDD **commission CSVs** become point lists—RPM reduces LAN chatter vs naive one-read-per-point Python loops.

## Mini Examples

- Poll 3 points for 3 iterations; log timestamp with `chrono` if in examples.
- Stop loop on Ctrl+C (`ctrlc` crate optional).

## Micro Exercises

1. Estimate BACnet traffic: 10 points × RPM vs 10 ReadProperty calls.
2. Store last values in `HashMap<String, f64>`.
3. Capture 60s pcap during poll—count UDP packets.

## Key Takeaway

**Batch at the protocol level**—network programming *and* BACnet smarts.

## Wireshark Lab

```bash
PCAP_SECONDS=60 ./capture_pcap.sh day43-rpm "udp port 47808 and host 192.168.204.200"
```

Filter: **`udp.port == 47808`** — use **Statistics → IO Graph** for packet rate.

---

## Python companion — RPM & poll loop

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab` (create if needed).*

```python
import time

points = ["analogInput:1", "analogInput:2", "analogValue:1"]
# bacnet = BAC0.lite()
for _ in range(3):
    # for p in points:
    #     print(p, bacnet.read(f"192.168.204.200 {p} presentValue"))
    # Prefer RPM/batch APIs when available — fewer UDP round trips
    time.sleep(60)
```

| Rust (main lesson) | Python |
|--------|--------|
| RPM-style batch API | BAC0 RPM / multi-read helpers |
| `tokio::time::sleep` / `thread::sleep` | `time.sleep` |
| `HashMap` last-value cache | `dict` of point → value |
| poll loop for historians | same edge pattern |

**Takeaway:** Batch reads cut LAN chatter—whether Rust RPM or Python multi-read, poll loops belong at the protocol layer.
