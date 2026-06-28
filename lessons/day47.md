## Day 47 – Async Rust Preview (tokio & BACnet)

### Goal

See why rusty-bacnet examples often use **`async`/`await`** and **`tokio`**—without becoming an async expert yet.

### Concept

```rust
#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // let reply = client.read(...).await?;
    Ok(())
}
```

**async** lets one thread wait on many UDP/HTTP operations—useful on gateways polling BACnet + Haystack + Modbus.

Sync vs async rule of thumb:

- Sync: fine for labs and single-device tools
- Async: edge services with many concurrent I/O tasks

### Why This Matters

Open-FDD bridge services multiplex drivers—async runtime is structural, not trendy.

### Mini examples

- Add `.await` to one example; read compiler errors if you forget `async fn`.
- Compare `thread::sleep` blocking vs `tokio::time::sleep` in async context.

### Micro exercises

1. When would blocking UDP recv freeze an async service?
2. Run `cargo tree | head`—spot `tokio` in dependency graph.
3. One paragraph: Python asyncio vs Rust tokio similarities.

### Key takeaway

**Learn sync sockets first (Days 36–37), async second**—same order as many networking courses, then production stacks.
