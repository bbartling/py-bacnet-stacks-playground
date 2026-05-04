## Day 28 – Linear Search (first match in trend data)

### Goal

Implement **linear search**: scan a sequence in order until you find a target or finish the list. Frame it with **HVAC examples** (first over-temp, first matching point name).

### Concept

**Linear search** is \(O(n)\): in the worst case you inspect every element. That is acceptable for small BACnet point lists or short trend slices and is exactly how “find first occurrence” works on **unsorted** data.

### How to use it

```python
def linear_search_index(seq, target):
    """Return first index where seq[i] == target, else -1."""
    for i, item in enumerate(seq):
        if item == target:
            return i
    return -1


def first_index_above_threshold(temps_f, limit_f):
    """First index where temperature exceeds limit, else -1."""
    for i, t in enumerate(temps_f):
        if t > limit_f:
            return i
    return -1


sat_f = [72.1, 73.0, 78.4, 77.9, 74.0]
print(first_index_above_threshold(sat_f, 76.0))  # 2
```

### Why this matters

Unsorted trend exports and ad-hoc lists from gateways are common. Linear search answers: **“When did we first cross this limit?”** and **“Does this device name appear in this list?”**—building blocks for simple diagnostics before you add rolling windows or physics models.

### Mini examples

- Return `True`/`False` for “is `device_id` in this list?” using a loop (same logic as `in` on a list).
- Find the first **static pressure** below a low alarm threshold (similar loop, different comparison).
- Search a list of small dicts `{"name": ..., "value": ...}` for the first dict whose `name` matches `"SAT"`.

### Micro exercises

1. Write `first_negative_index(flows)` returning the first index where airflow (cfm) is negative, or `-1`.
2. Given parallel lists `timestamps` and `oat` of the same length, return the **timestamp** at the first index where `oat < 35.0` (freezing concern), or `None` if never.
3. Extend linear search to return **all** indices where `target` occurs (still one pass; append to a list).

### Key takeaway

Linear search = inspect in order, stop early when possible. For HVAC lists, it is the straightforward way to locate **first faults** or **first excursions** without sorting.
