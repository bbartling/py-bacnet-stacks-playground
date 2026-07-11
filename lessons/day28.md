# Day 28 – Rust recap & ownership crash course

*Week 5 — Rust fast track begins. You should already have Rust installed from **Day 1** and have run the **Rust companion** blocks on Days 1–27.*

## Goal

Confirm your Rust toolchain, review what Days 1–27 already taught, and learn **ownership, borrowing, and lifetimes** in plain language so Days 29–34 are practice—not a cliff.

If you **skipped** the Rust companions: do **Day 1 Rust companion** (install + `cargo new`) today, then skim Days 2, 6, 8, 9, 11, 15, 18, and 27 companions before continuing.

## Concept

| Topic | Where you saw it | Rust words |
|-------|------------------|------------|
| Install / run | Day 1 | `rustup`, `cargo run` |
| Variables | Day 2 | `let`, `let mut` |
| Strings | Day 3 | `String`, `&str` |
| Numbers / bool | Day 4 | `i32`, `f64`, `bool` |
| Print / input | Day 5 | `println!`, `read_line` |
| Lists | Days 6–7 | `Vec<T>` |
| Loops | Days 8, 14 | `for`, `while`, `break` |
| `if` | Day 9 | `if` / `else` (expressions) |
| Dicts | Days 11–12 | `HashMap` |
| Functions | Day 15 | `fn name(x: T) -> R` |
| Files | Day 17 | `std::fs` |
| Errors | Day 18 | `Option`, `Result` |
| Structs lite | Day 22 | `struct` |
| Ownership teaser | Day 27 | move vs `&` borrow |

**Quick health check** (should already work):

```bash
rustc --version && cargo --version
cd ~/rust-lab
cargo new day28_ownership --bin
cd day28_ownership && cargo run
```

### Ownership (the big idea)

In Python, the garbage collector cleans up. In Rust, **each value has exactly one owner**. When the owner goes out of scope, Rust frees the memory. No GC pause, no use-after-free.

```rust
fn main() {
    let a = String::from("AHU-1"); // a owns the String
    let b = a;                     // ownership MOVES to b
    // println!("{a}");            // ERROR: a was moved
    println!("{b}");               // OK
}
```

**Copy types** (small, on the stack) do *not* move — they copy: `i32`, `f64`, `bool`, `char`.

```rust
let x = 72;
let y = x;      // copy
println!("{x} {y}"); // both OK
```

### Borrowing (using without taking)

Borrow = temporary access with `&` (shared) or `&mut` (exclusive write).

```rust
fn print_name(name: &str) {   // borrows, does not own
    println!("{name}");
}

fn bump(pv: &mut f64) {       // exclusive borrow
    *pv += 1.0;               // * = dereference
}

fn main() {
    let tag = String::from("SAT");
    print_name(&tag);         // lend tag
    print_name(&tag);         // can lend again (shared)
    println!("still own: {tag}");

    let mut temp = 70.0;
    bump(&mut temp);
    println!("{temp}");
}
```

**Rules (enforced by compiler):**

1. Many shared borrows (`&T`) **or** one mutable borrow (`&mut T`) — not both at once.
2. Borrows must not outlive the owner.

That is why network code often takes `&[u8]` or `&str`: “read this buffer, don’t free it.”

### Lifetimes (only the intuition)

A **lifetime** is “how long this reference is valid.” You rarely write them at first; the compiler infers them.

```rust
// Both references must live at least as long as the function needs them.
fn longer<'a>(x: &'a str, y: &'a str) -> &'a str {
    if x.len() >= y.len() { x } else { y }
}
```

Read `'a` as “some lifetime the caller already has.” You will see `'a` in library docs; you do not need to invent fancy lifetimes for Day 29–40 labs.

### Move into functions

```rust
fn take(s: String) { /* owns s, drops at end */ }

fn main() {
    let name = String::from("VAV");
    take(name);
    // name is gone — pass &name if you still need it
}
```

Prefer:

```rust
fn use_name(s: &str) { println!("{s}"); }
```

so the caller keeps ownership.

## Why This Matters

BACnet/Haystack clients pass **buffers and strings** around constantly. Ownership/borrowing is how Rust stays fast and safe without a GC. Days 29–31 practice types, control flow, and `Result` on top of this foundation.

## Mini Examples

- Clone when you truly need two owners: `let b = a.clone();`
- Slice a string (ASCII): `let head = &s[0..3];` (this is a borrow)
- Return a reference only to data the caller already owns (lifetime ties them together)

## Micro Exercises

1. In `day28_ownership`, create a `String`, move it into a second variable, and confirm the first cannot print (comment the error).
2. Write `fn label(device: u32, point: &str) -> String` using `format!`.
3. Write `fn add_one(x: &mut i32)` and call it on a `mut` variable.
4. In one sentence: when do you use `&str` vs `String`?

## Key Takeaway

**Owner frees memory. `&` borrows. `&mut` exclusive write. Lifetimes keep borrows honest.**  
Days 1–27 already gave you syntax; Day 28 is the memory model. Day 29 continues with types and BACnet-style readings—no surprise install step.

---

## Python companion — Ownership vs GC

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab` (create if needed).*

```python
# Python: assignment aliases the same object (GC cleans up later)
a = {"device": "AHU-1", "pv": 72.5}
b = a                    # b is another name for the same dict
b["pv"] = 73.0
print(a["pv"])           # 73.0 — both see the change

readings = [71.0, 72.0]
copy = list(readings)    # new list; like Rust .clone() for the container
copy.append(73.0)
print(readings)          # [71.0, 72.0] — original unchanged
```

| Rust (main lesson) | Python |
|--------|--------|
| move transfers ownership | assignment usually aliases (same object) |
| GC not used — owner drops | GC frees when no references remain |
| `&T` / `&mut T` borrows | pass object; mutate carefully or copy |
| `.clone()` for a second owner | `list(x)`, `dict(x)`, or `copy.copy` |

**Takeaway:** Rust moves; Python aliases—know which name mutates a shared point cache before you blame the BACnet driver.
