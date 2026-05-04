## Day 31 – Ordering data (sorting for setpoints, rankings, and medians)

### Goal

Use Python’s **`sorted()`** and **`list.sort()`** with `key` and `reverse` to rank **HVAC-related records**. See a tiny **bubble sort** only as a teaching toy—production code should use Timsort via the built-ins.

### Concept

**Sorting** orders data so you can pick medians, percentiles, or “worst zones first.” Python’s sort is highly optimized (\(O(n \log n)\)). **Bubble sort** repeatedly swaps neighbors; it is \(O(n^2)\) and mainly useful to appreciate **why** good libraries matter.

### How to use it

```python
# Zone temperature error (actual - setpoint); rank worst first
zones = [("Z1", 0.5), ("Z2", -1.2), ("Z3", 2.1), ("Z4", 0.1)]
by_error = sorted(zones, key=lambda z: abs(z[1]), reverse=True)
print(by_error)  # [('Z3', 2.1), ('Z2', -1.2), ...]

def median_sorted(values):
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2

oat = [38, 40, 35, 39, 41]
print(median_sorted(oat))
```

**Bubble sort (optional lab only):**

```python
def bubble_sort_asc(lst):
    a = list(lst)
    n = len(a)
    for i in range(n):
        swapped = False
        for j in range(n - 1 - i):
            if a[j] > a[j + 1]:
                a[j], a[j + 1] = a[j + 1], a[j]
                swapped = True
        if not swapped:
            break
    return a
```

### Why this matters

You might sort VAVs by **reheat valve position** during unoccupied hours, SAT samples to compute a **median** for stable thresholds, or order alarms by **severity** then **time**. Median and order statistics resist a single bad sensor spike better than a naive max.

### Mini examples

- Sort dicts `{"zone": "...", "deviation_f": ...}` by `deviation_f`.
- Sort timestamps paired with values (list of tuples) by time for plotting prep.
- Compare bubble sort vs `sorted()` on \(n=200\) random floats (time discussion only—no formal big-O proof required).

### Micro exercises

1. Given static pressure readings, return the **middle two averaged** median for even length (reuse `median_sorted` pattern).
2. Sort a list of `(ahu_name, kw)` by **descending** `kw` to rank energy users for a report.
3. Explain in one sentence why you would **not** ship bubble sort to production for 10,000-point files.

### Key takeaway

For real work: **`sorted` / `sort` + `key`**. Bubble sort is pedagogy. Sorting unlocks **ranking** and **robust statistics** for HVAC telemetry.
