## Day 44 – WriteProperty & Priority Array (Careful Lab)

### Goal

Understand **WriteProperty** and **priority** in rusty-bacnet—**lab/simulator only** unless you have permission on live equipment.

### Concept

BACnet writes target a **priority level** (1–16). Releasing to schedule often means writing **NULL** at priority 8 (vendor patterns vary—verify on your device doc).

```rust
// NEVER run against production without change control
// client.write_property(..., priority: 8, value: ...)?;
```

Always read back **priority-array** and **present-value** after a test write.

### Why This Matters

Rust makes it easy to ship powerful tools—**discipline** matters more than language.

### Mini examples

- Document your site policy: who approves writes?
- Read priority array without writing anything.

### Micro exercises

1. Explain difference between **present-value** and priority 8 slot in prose.
2. PCAP: can you see WriteProperty in Wireshark? (filter `bacnet`)
3. If no write-safe point exists, simulate with a local BACnet simulator instead.

### Key takeaway

**Read-only mastery first.** Writes in Rust are the same responsibility as writes in Python or Workbench.

### Wireshark Lab

If using simulator write test:

Filter: **`bacnet.type == 0x0f`** (confirm type in your Wireshark version for WriteProperty).
