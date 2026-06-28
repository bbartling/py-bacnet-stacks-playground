## Day 29 – Rust Types, Operators & Variables

### Goal

Learn Rust **scalars** (`i32`, `f64`, `bool`, `char`), **mutability**, and operators—enough to format BACnet-style readings in `println!`.

### Concept

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

### Why This Matters

BACnet object IDs and present values map cleanly to `u32` and `f64`. Explicit types prevent silent rounding bugs in control math.

### Mini examples

- Store OAT as `f64`, SAT as `f64`, compute delta.
- Use `{:.2}` formatting for trend-like output.

### Micro exercises

1. Declare `let port: u16 = 47808;` and print it (BACnet/IP default).
2. What happens if you try `present_value = 80.0` without `mut`? Read the compiler error.
3. Write an expression: `sat > 55.0 && oat < 40.0` as a `bool`.

### Key takeaway

Rust forces you to **choose numeric types** and **declare mutability**—annoying at first, invaluable when a gateway runs for months without restarts.
