# Day 31 – Functions, Option & Result

## Goal

Write reusable functions and handle **missing data** (`Option`) and **errors** (`Result`)—the Rust patterns every network client uses.

## Concept

```rust
fn parse_pv(text: &str) -> Result<f64, std::num::ParseFloatError> {
    text.trim().parse::<f64>()
}

fn first_ok(values: &[Option<f64>]) -> Option<f64> {
    values.iter().find_map(|v| *v)
}

fn main() {
    match parse_pv("72.5") {
        Ok(v) => println!("pv = {v}"),
        Err(e) => eprintln!("bad pv: {e}"),
    }
}
```

- **`Option<T>`**: `Some(x)` or `None`
- **`Result<T, E>`**: `Ok(x)` or `Err(e)`
- **`?` operator** (later): propagate errors up the call stack

## Why This Matters

A BACnet read can **timeout**, return **ERROR**, or give a value. Rust makes you handle that in the type system instead of `None` surprises at 2 a.m.

## Mini Examples

- Function `c_to_f(c: f64) -> f64`
- Return `None` when a CSV field is empty string.

## Micro Exercises

1. Write `fn device_label(id: u32) -> String` using `format!`.
2. Write `parse_u32(s: &str) -> Option<u32>`.
3. Explain in one sentence: when would you use `Option` vs `Result`?

## Key Takeaway

Network code lives on **`Result`**. Get comfortable before UDP sockets and HTTP clients.

---

## Python companion — functions, None & errors

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab` (create if needed).*

```python
def parse_pv(text: str) -> float:
    return float(text.strip())

def first_ok(values: list[float | None]) -> float | None:
    for v in values:
        if v is not None:
            return v
    return None

try:
    print("pv =", parse_pv("72.5"))
except ValueError as e:
    print("bad pv:", e)
```

| Rust (main lesson) | Python |
|--------|--------|
| `Option<T>` / `None` | `T \| None` / `None` |
| `Result<T, E>` | `try`/`except` (or return `(ok, err)`) |
| `.parse::<f64>()` | `float(s)` raises `ValueError` |
| `?` propagate | raise or return `None` / re-raise |

**Takeaway:** A timed-out BACnet read is `None` or an exception—handle it explicitly so night-shift logs stay honest.
