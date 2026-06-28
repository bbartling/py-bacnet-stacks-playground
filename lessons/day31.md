## Day 31 – Functions, Option & Result

### Goal

Write reusable functions and handle **missing data** (`Option`) and **errors** (`Result`)—the Rust patterns every network client uses.

### Concept

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

### Why This Matters

A BACnet read can **timeout**, return **ERROR**, or give a value. Rust makes you handle that in the type system instead of `None` surprises at 2 a.m.

### Mini examples

- Function `c_to_f(c: f64) -> f64`
- Return `None` when a CSV field is empty string.

### Micro exercises

1. Write `fn device_label(id: u32) -> String` using `format!`.
2. Write `parse_u32(s: &str) -> Option<u32>`.
3. Explain in one sentence: when would you use `Option` vs `Result`?

### Key takeaway

Network code lives on **`Result`**. Get comfortable before UDP sockets and HTTP clients.
