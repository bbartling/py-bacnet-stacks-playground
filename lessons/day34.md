# Day 34 – Ownership & Borrowing (practice)

## Goal

Practice the **borrow checker** (from Day 28 and the Day 1–27 Rust companions): pass `&str` into functions and store data in structs without fighting the compiler.

## Concept

```rust
fn log_tag(tag: &str, val: f64) {
    println!("{tag} = {val}");
}

fn main() {
    let name = String::from("OA-T");
    log_tag(&name, 55.3);  // borrow &name as &str
    println!("still own {name}");
}
```

Rules (simplified):

1. One **mutable** borrow *or* many **immutable** borrows at a time
2. References must not outlive the data they point to
3. **`clone()`** when you truly need a copy

## Why This Matters

Socket buffers and HTTP bodies are **borrowed slices** (`&[u8]`, `&str`). Fighting ownership early makes rusty-bacnet examples click.

## Mini Examples

- Fix a "borrow of moved value" compiler error by using `.clone()` or references.
- Function taking `&[f64]` instead of `Vec<f64>`.

## Micro Exercises

1. Explain why `let s2 = s1; println!("{s1}")` fails for `String`.
2. Write `fn avg(vals: &[f64]) -> Option<f64>`.
3. Read one rusty-bacnet example; circle every `&` and `&mut` in comments.

## Key Takeaway

**Borrow instead of clone** in hot paths (polling loops). Clone when building persistent caches.

## Wireshark Lab

No capture today—read [wireshark_filters.md](./lab-scripts/wireshark_filters.md) so Day 36 feels familiar.

---

## Python companion — aliases & copies

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab` (create if needed).*

```python
def log_tag(tag: str, val: float) -> None:
    print(f"{tag} = {val}")

name = "OA-T"                 # str is immutable; "borrow" is just pass-by-object
log_tag(name, 55.3)
print("still have", name)

def avg(vals: list[float]) -> float | None:
    return sum(vals) / len(vals) if vals else None

temps = [68.0, 71.0, 74.0]
print(avg(temps))             # pass the list; don't need & — but mutations are shared
```

| Rust (main lesson) | Python |
|--------|--------|
| `&str` / `&[f64]` borrows | pass object; caller keeps the name |
| move of `String` | rebind / mutate; no move semantics |
| `.clone()` | `list(x)` / `x.copy()` when you need isolation |
| borrow checker | discipline + immutables (`tuple`, `str`) |

**Takeaway:** Python won't stop you from mutating a shared poll buffer—treat aliases like borrows when you cache point values.
