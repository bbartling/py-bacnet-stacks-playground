## Day 34 – Ownership & Borrowing (practice)

### Goal

Practice the **borrow checker** (from Day 28 and the Day 1–27 Rust companions): pass `&str` into functions and store data in structs without fighting the compiler.

### Concept

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

### Why This Matters

Socket buffers and HTTP bodies are **borrowed slices** (`&[u8]`, `&str`). Fighting ownership early makes rusty-bacnet examples click.

### Mini examples

- Fix a "borrow of moved value" compiler error by using `.clone()` or references.
- Function taking `&[f64]` instead of `Vec<f64>`.

### Micro exercises

1. Explain why `let s2 = s1; println!("{s1}")` fails for `String`.
2. Write `fn avg(vals: &[f64]) -> Option<f64>`.
3. Read one rusty-bacnet example; circle every `&` and `&mut` in comments.

### Key takeaway

**Borrow instead of clone** in hot paths (polling loops). Clone when building persistent caches.

### Wireshark Lab

No capture today—read [wireshark_filters.md](./lab-scripts/wireshark_filters.md) so Day 36 feels familiar.
