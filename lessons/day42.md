# Day 42 – ReadProperty in Rust (Device 5007)

## Goal

Issue a **ReadProperty** for `present-value` on an analog object using rusty-bacnet (or a thin wrapper binary you write).

## Concept

Target (adjust to your commission CSV):

- Device ID: **5007**
- Network: `192.168.204.200`
- Example object: `analogInput:1` present-value

Pseudocode shape:

```rust
// Follow your clone's API — names differ by version
// let client = BacnetClient::bind("0.0.0.0:47808")?;
// let pv = client.read_property(device, object, PropertyIdentifier::PresentValue).await?;
// println!("pv = {pv:?}");
```

Log **`Result`** errors—timeouts look different from **Error** PDUs in pcaps.

## Why This Matters

This is the Rust equivalent of your Day 1–10 Python reads—same field skill, new toolchain.

## Mini Examples

- Read `object-name` and `present-value` for the same object.
- Print raw enum for **units** if available.

## Micro Exercises

1. Capture pcap during read—match Wireshark decode to printed value.
2. Handle timeout with a friendly message (no panic).
3. Write lab notes: object id string you used.

## Key Takeaway

**One successful ReadProperty in Rust** proves the whole toolchain: Cargo, UDP, BACnet, bench routing.

## Wireshark Lab

Filter: **`bacnet && ip.addr == 192.168.204.200`**

Find **Complex-ACK** vs **Error** APDU in the tree.

---

## Python companion — ReadProperty with BAC0

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab` (create if needed).*

```python
# Adjust object string to your commission CSV
# import BAC0
# bacnet = BAC0.lite()
# pv = bacnet.read("192.168.204.200 analogInput:1 presentValue")
# print("pv =", pv)
print("Match Wireshark Complex-ACK to the printed present-value.")
```

| Rust (main lesson) | Python |
|--------|--------|
| rusty-bacnet ReadProperty | `BAC0.read(...)` |
| `Result` timeout vs Error PDU | exceptions / `None` — still check pcap |
| device 5007 @ `.200` | same bench target |
| `PropertyIdentifier::PresentValue` | `"presentValue"` in BAC0 string |

**Takeaway:** One successful present-value read—Python or Rust—proves routing; the pcap proves which APDU you got.
