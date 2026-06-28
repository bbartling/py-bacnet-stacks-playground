## Day 30 – Control Flow: if, loop, match

### Goal

Branch and iterate like Python `if`/`for`, but with **`match`** for exhaustive enum-style logic.

### Concept

```rust
fn classify_sat(sat: f64) -> &'static str {
    if sat > 55.0 {
        "high"
    } else if sat < 45.0 {
        "low"
    } else {
        "ok"
    }
}

fn main() {
    for i in 0..5 {
        println!("sample {}", i);
    }
    let code = 2;
    match code {
        0 => println!("normal"),
        1 | 2 => println!("warning"),
        _ => println!("unknown"),
    }
}
```

### Why This Matters

Control sequences are **state machines**. `match` makes BACnet priority levels and alarm severities explicit—compiler warns if you forget a case.

### Mini examples

- Loop over `[68.0, 71.0, 74.0]` and print `classify_sat` for each.
- Use `while` to simulate a 3-iteration poll loop.

### Micro exercises

1. Write `match` on priority `1..=16` that prints "manual" only for priority 8.
2. Convert a Python-style `for x in list` mental model: what is `0..3` vs `0..=3`?
3. Refactor nested `if` into `match` on a small enum you define.

### Key takeaway

**`match` is your friend** for BACnet enums (object types, error codes) later in rusty-bacnet labs.
