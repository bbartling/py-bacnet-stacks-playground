# Day 30 – Control Flow: if, loop, match

## Goal

Branch and iterate like Python `if`/`for`, but with **`match`** for exhaustive enum-style logic.

## Concept

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

## Why This Matters

Control sequences are **state machines**. `match` makes BACnet priority levels and alarm severities explicit—compiler warns if you forget a case.

## Mini Examples

- Loop over `[68.0, 71.0, 74.0]` and print `classify_sat` for each.
- Use `while` to simulate a 3-iteration poll loop.

## Micro Exercises

1. Write `match` on priority `1..=16` that prints "manual" only for priority 8.
2. Convert a Python-style `for x in list` mental model: what is `0..3` vs `0..=3`?
3. Refactor nested `if` into `match` on a small enum you define.

## Key Takeaway

**`match` is your friend** for BACnet enums (object types, error codes) later in rusty-bacnet labs.

---

## Python companion — if, for, match-like logic

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab` (create if needed).*

```python
def classify_sat(sat: float) -> str:
    if sat > 55.0:
        return "high"
    if sat < 45.0:
        return "low"
    return "ok"

for i in range(5):
    print("sample", i)

code = 2
match code:                    # 3.10+ structural match
    case 0:
        print("normal")
    case 1 | 2:
        print("warning")
    case _:
        print("unknown")
```

| Rust (main lesson) | Python |
|--------|--------|
| `if` is an expression | `if` is a statement (`x if c else y`) |
| `for i in 0..5` | `for i in range(5)` |
| `match` exhaustive | `match`/`case` (3.10+) or `if`/`elif` |
| `_` wildcard | `_` in `case _` |

**Takeaway:** Alarm severities and priority bands map cleanly to `match`/`case`—same state-machine habit as Rust, friendlier syntax.
