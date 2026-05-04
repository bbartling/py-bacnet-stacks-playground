## Day 29 – Min, max, and “extreme event” scanning

### Goal

Implement **minimum** and **maximum** with a single forward scan (accumulator pattern). Use **HVAC readings** (duct static, supply temp, zone deltas) as mental models.

### Concept

Initialize `best` to the first element, then for each remaining value compare and update. That is one form of **reduction**: many values → one summary. Same pattern finds **longest run** later with a small change of state.

### How to use it

```python
def find_min(values):
    if not values:
        return None
    smallest = values[0]
    for v in values[1:]:
        if v < smallest:
            smallest = v
    return smallest


def find_max(values):
    if not values:
        return None
    largest = values[0]
    for v in values[1:]:
        if v > largest:
            largest = v
    return largest


static_inwg = [1.2, 1.15, 1.08, 1.11, 1.09]
print(find_min(static_inwg), find_max(static_inwg))
```

### Why this matters

Operators care about **peak SAT** during a demand event, **minimum discharge air** during economizer operation, or **max zone deviation** during occupied hours. Knowing the scan pattern lets you add rules (“ignore readings when fan command is zero”) without reaching for a library.

### Mini examples

- Single pass: return `(min_val, max_val)` for a non-empty list of floats.
- Track **index** of max as well as value (useful to align with timestamps in parallel lists).
- Compare **two** lists of same length element-wise and return the max **absolute difference** (simple loop; no NumPy).

### Micro exercises

1. Write `max_abs_deviation(setpoints, actuals)` assuming equal-length lists of floats.
2. Verify your `find_min` / `find_max` match Python’s `min()` / `max()` on a random list of 10 integers.
3. **Stretch (still CS 101):** return `(min_val, min_index, max_val, max_index)` in one pass.

### Key takeaway

Min/max are accumulator algorithms. They mirror how many **AFDD** summaries are computed on bounded windows—same idea, smaller code.
