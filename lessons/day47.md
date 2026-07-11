# Day 47 – Async Rust Preview (tokio & BACnet)

## Goal

See why rusty-bacnet examples often use **`async`/`await`** and **`tokio`**—without becoming an async expert yet.

## Concept

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

## Why This Matters

Open-FDD bridge services multiplex drivers—async runtime is structural, not trendy.

## Mini Examples

- Add `.await` to one example; read compiler errors if you forget `async fn`.
- Compare `thread::sleep` blocking vs `tokio::time::sleep` in async context.

## Micro Exercises

1. When would blocking UDP recv freeze an async service?
2. Run `cargo tree | head`—spot `tokio` in dependency graph.
3. One paragraph: Python asyncio vs Rust tokio similarities.

## Key Takeaway

**Learn sync sockets first (Days 36–37), async second**—same order as many networking courses, then production stacks.

---

## Python companion — asyncio sketch

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
import asyncio

async def poll_once(name: str) -> str:
    await asyncio.sleep(0.05)  # stand-in for I/O
    return f"{name} ok"

async def main() -> None:
    a, b = await asyncio.gather(poll_once("bacnet"), poll_once("haystack"))
    print(a, b)

asyncio.run(main())
```

| Rust (main lesson) | Python |
|--------|--------|
| `#[tokio::main]` + `.await` | `asyncio.run` + `async def` |
| `tokio::time::sleep` | `asyncio.sleep` |
| many concurrent I/O tasks | `asyncio.gather` |

**Takeaway:** Same idea—don't block the event loop; Rust uses tokio, Python uses asyncio.
