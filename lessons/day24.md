# Day 24 – any(), all() & Simple Patterns

*Part III: Data Structures | Week 4*

## Goal

Explore Python's `any()` and `all()` functions for checking conditions over collections. Use loops to build the data you pass to them — no comprehensions or generator expressions.

## Concept

The built-in functions `all()` and `any()` take an iterable and return a Boolean. `all()` returns `True` if every element is truthy (or if the iterable is empty). `any()` returns `True` if at least one element is truthy and `False` if the iterable is empty. Use a loop to build a list of Booleans, then pass it to `any()` or `all()`.

## How to Use It

**`all()` and `any()` with a loop:**

```python
readings = [72, 71, 69, 73]

# check if all readings are above 65
above_65 = []
for r in readings:
    above_65.append(r > 65)
print(all(above_65))  # True

# check if any reading is above 72
above_72 = []
for r in readings:
    above_72.append(r > 72)
print(any(above_72))  # True
```

**Shorter pattern with a loop:**

```python
# all above 65?
all_ok = True
for r in readings:
    if r <= 65:
        all_ok = False
        break
print(all_ok)
```

## Why This Matters

Functions like `any()` and `all()` simplify checks over collections. When validating sensor readings or point lists, you often need to ask "are all values in range?" or "is any value in alarm?". Using loops to build the conditions keeps the logic explicit.

## Mini Examples

- Use a loop and `any()` to check whether any point in a list has a reading above 80.
- Use a loop and `all()` to verify that all device IDs in a list are greater than 0.
- Check if all temperatures in a dictionary are between 65 and 75.

## Micro Exercises

1. Given `values = [0, 1, 2, 3]`, use a loop to build a list and pass it to `any()` to check if any value is negative. Use another loop for `all()` to check if all values are less than 10.
2. Write a function `all_in_range(readings, low, high)` that returns `True` if every reading is between `low` and `high` inclusive.
3. Write a function `any_alarm(readings, threshold)` that returns `True` if any reading exceeds the threshold.

## Key Takeaway

`all()` returns `True` only if every element is truthy. `any()` returns `True` if at least one element is truthy. Use loops to build the conditions you pass to them — clear and easy to debug.

---

## Rust companion — `any` / `all` on iterators

*Same day as the Python lesson above. Work in `~/rust-lab` (create on Day 1).*

```rust
fn main() {
    let alarms = [false, false, true];
    let any_alarm = alarms.iter().any(|&a| a);
    let all_ok = alarms.iter().all(|&a| !a);
    println!("any_alarm={any_alarm} all_ok={all_ok}");
}
```

**Takeaway:** Iterator adapters read like English and avoid manual loops.

