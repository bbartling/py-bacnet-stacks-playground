# Day 45 – Who-Is / I-Am Device Discovery Scan

## Goal

Build or run a **discovery scan** listing device IDs and addresses—Rust replacement for Python Who-Is apps.

## Concept

Discovery flow:

1. Send **Who-Is** (global or range)
2. Collect **I-Am** responses into `HashMap<u32, SocketAddr>`
3. Print table sorted by device id

```rust
// for (id, addr) in devices.iter() {
//     println!("{id} @ {addr}");
// }
```

## Why This Matters

Commissioning starts with **what's on the wire**—same as vibe_code_apps discovery checkpoints.

## Mini Examples

- Limit scan to device range `5000-5010`.
- Compare scan results to your known `5007` bench device.

## Micro Exercises

1. Run scan while capturing pcap—count I-Am packets.
2. Export device list to CSV from Rust (`writeln!` is enough).
3. Merge duplicate I-Ams—why might you see two?

## Key Takeaway

**Discovery is UDP broadcast/multicast behavior**—routing issues show up here first.

## Wireshark Lab

Filter: **`bacnet && bacnet.bvlc.function == 0x0b`** (Who-Is / I-Am family—verify field names in your Wireshark build).

---

## Python companion — Who-Is / I-Am scan

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab` (create if needed).*

```python
# import BAC0
# bacnet = BAC0.lite()
# devices = bacnet.whois()           # collect I-Am responses
# for d in sorted(devices or [], key=lambda x: x[0] if isinstance(x, tuple) else x):
#     print(d)
print("Discovery is UDP broadcast—capture while whois() runs.")
```

| Rust (main lesson) | Python |
|--------|--------|
| Who-Is → `HashMap<u32, SocketAddr>` | `whois()` → device list / dict |
| print sorted device table | same commissioning table |
| range-limited Who-Is | BAC0 range args when supported |
| duplicate I-Ams | same on the wire |

**Takeaway:** Commissioning starts with what's on the wire—Python Who-Is and Rust discovery scans chase the same I-Am replies.
