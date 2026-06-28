## Day 33 – Vec, HashMap & String

### Goal

Use **`Vec`**, **`HashMap`**, and **`String`**—the collections you'll use to cache device lists and tag maps.

### Concept

```rust
use std::collections::HashMap;

fn main() {
    let mut readings: Vec<f64> = vec![71.2, 72.0, 71.8];
    readings.push(72.5);
    let mut by_device: HashMap<u32, String> = HashMap::new();
    by_device.insert(5007, "AHU-1".into());
    if let Some(name) = by_device.get(&5007) {
        println!("{name}: avg {:.2}", readings.iter().sum::<f64>() / readings.len() as f64);
    }
}
```

- **`String`** vs **`&str`**: owned vs borrowed text
- **`.iter()`**, **`.push()`**, **`.get()`**

### Why This Matters

Who-Is responses and Haystack `/read` results become **`HashMap` caches** on an edge agent.

### Mini examples

- Count how many readings exceed 72.0 using a loop (no itertools yet).
- Build `HashMap<&str, f64>` of sensor name → value from two parallel vectors.

### Micro exercises

1. Sort `readings` with `readings.sort_by(|a,b| a.partial_cmp(b).unwrap())`.
2. Remove a key from a map safely with `.remove`.
3. When would you store `String` keys vs `u32` device IDs?

### Key takeaway

**Vec + HashMap** replace Python lists and dicts—learn them before parsing network responses into memory.
