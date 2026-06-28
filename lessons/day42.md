## Day 42 – ReadProperty in Rust (Device 5007)

### Goal

Issue a **ReadProperty** for `present-value` on an analog object using rusty-bacnet (or a thin wrapper binary you write).

### Concept

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

### Why This Matters

This is the Rust equivalent of your Day 1–10 Python reads—same field skill, new toolchain.

### Mini examples

- Read `object-name` and `present-value` for the same object.
- Print raw enum for **units** if available.

### Micro exercises

1. Capture pcap during read—match Wireshark decode to printed value.
2. Handle timeout with a friendly message (no panic).
3. Write lab notes: object id string you used.

### Key takeaway

**One successful ReadProperty in Rust** proves the whole toolchain: Cargo, UDP, BACnet, bench routing.

### Wireshark Lab

Filter: **`bacnet && ip.addr == 192.168.204.200`**

Find **Complex-ACK** vs **Error** APDU in the tree.
