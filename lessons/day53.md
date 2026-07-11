# Day 53 – Correlate Haystack Tags with BACnet Points

## Goal

Build a **mapping table** (CSV or Rust struct) linking Haystack `id` ↔ BACnet `device:object` for one AHU on your bench.

## Concept

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

## Why This Matters

Multi-protocol gateways need **one logical point identity**—RDF weeks formalize this; today you do it in a table.

## Mini Examples

- Map OA-T Haystack tag to BACnet AI if both exist.
- Note unmapped points—document why.

## Micro Exercises

1. Five-row CSV `haystack_id,bacnet_obj,pv_haystack,pv_bacnet,delta`.
2. If deltas differ, hypothesis: stale cache vs unit mismatch.
3. Dual capture: BACnet UDP + Haystack HTTPS same minute.

## Wireshark Lab

```bash
./capture_pcap.sh day53-dual "udp port 47808 or (tcp port 443 and host 192.168.204.11)"
```

Filters separately: **`udp.port == 47808`** and **`tcp.port == 443`**

## Key Takeaway

**Interoperability is mapping**, not magic—Rust holds the table; RDF will name relationships properly.

---

## Python companion — Mapping CSV sketch

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
import csv

rows = [
    {"haystack_id": "@ahu1.oa-t", "bacnet_obj": "5007:AI:1", "pv_h": 55.3, "pv_b": 55.2},
]
for r in rows:
    r["delta"] = round(r["pv_h"] - r["pv_b"], 2)

with open("point_map.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["haystack_id", "bacnet_obj", "pv_h", "pv_b", "delta"])
    w.writeheader()
    w.writerows(rows)
```

| Rust (main lesson) | Python |
|--------|--------|
| `PointMap` struct / CSV | `csv.DictWriter` sketch |
| dual-protocol alignment | same columns for intuition |
| RDF later | still a flat table today |

**Takeaway:** Mapping is a table first—Python can draft CSV; keep the durable map in the Rust toolchain.
