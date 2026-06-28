## Day 53 – Correlate Haystack Tags with BACnet Points

### Goal

Build a **mapping table** (CSV or Rust struct) linking Haystack `id` ↔ BACnet `device:object` for one AHU on your bench.

### Concept

```rust
struct PointMap {
    haystack_id: String,
    bacnet_device: u32,
    object_type: u16,
    instance: u32,
}
```

Workflow:

1. Haystack read → list temp points for equip
2. BACnet RPM → list analog inputs
3. Human or rules-assisted alignment (name patterns)

Open-FDD uses commission CSVs—same idea.

### Why This Matters

Multi-protocol gateways need **one logical point identity**—RDF weeks formalize this; today you do it in a table.

### Mini examples

- Map OA-T Haystack tag to BACnet AI if both exist.
- Note unmapped points—document why.

### Micro exercises

1. Five-row CSV `haystack_id,bacnet_obj,pv_haystack,pv_bacnet,delta`.
2. If deltas differ, hypothesis: stale cache vs unit mismatch.
3. Dual capture: BACnet UDP + Haystack HTTPS same minute.

### Key takeaway

**Interoperability is mapping**, not magic—Rust holds the table; RDF will name relationships properly.

### Wireshark Lab

```bash
./capture_pcap.sh day53-dual "udp port 47808 or (tcp port 443 and host 192.168.204.11)"
```

Filters separately: **`udp.port == 47808`** and **`tcp.port == 443`**
