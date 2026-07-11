# Day 29 – Rust Types, Operators & Variables

## Goal

Learn Rust **scalars** (`i32`, `f64`, `bool`, `char`), **mutability**, and operators—enough to format BACnet-style readings in `println!`.

## Concept

```rust
fn main() {
    let device_id: u32 = 5007;
    let mut present_value: f64 = 72.5;
    present_value += 0.25;
    let online = true;
    println!("dev {} pv {:.1} online {}", device_id, present_value, online);
}
```

- **`let`** binds immutably unless you write **`mut`**
- Integer types: `u8`, `u16`, `u32`, `i32`, `usize`
- Floats: `f32`, `f64`
- Comparisons: `==`, `!=`, `<`, `>`, `&&`, `||`, `!`

## Why This Matters

BACnet object IDs and present values map cleanly to `u32` and `f64`. Explicit types prevent silent rounding bugs in control math.

## Mini Examples

- Store OAT as `f64`, SAT as `f64`, compute delta.
- Use `{:.2}` formatting for trend-like output.

## Micro Exercises

1. Declare `let port: u16 = 47808;` and print it (BACnet/IP default).
2. What happens if you try `present_value = 80.0` without `mut`? Read the compiler error.
3. Write an expression: `sat > 55.0 && oat < 40.0` as a `bool`.

## Key Takeaway

Rust forces you to **choose numeric types** and **declare mutability**—annoying at first, invaluable when a gateway runs for months without restarts.

---

## Python companion — Types & variables

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab` (create if needed).*

```python
device_id = 5007              # int (arbitrary size)
present_value = 72.5          # float (always mutable binding)
present_value += 0.25
online = True
print(f"dev {device_id} pv {present_value:.1f} online {online}")
port = 47808                  # BACnet/IP default
print(sat := 56.0, sat > 55.0 and True)  # comparisons → bool
```

| Rust (main lesson) | Python |
|--------|--------|
| `let` / `let mut` | name always rebindable |
| `u32`, `f64`, `bool` | `int`, `float`, `bool` (runtime) |
| `{:.1}` in `println!` | f-string `{x:.1f}` |
| compile-time type check | `type()` / optional type hints |

**Takeaway:** Same BACnet IDs and present values—Python is looser on types; still pick clear names so OT math stays readable.
