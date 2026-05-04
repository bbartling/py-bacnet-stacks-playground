## Day 37 – Sliding windows with lists (running average, no Pandas)

### Goal

Compute a **running mean** (and optionally min/max) over the last `k` samples using **indexes and loops**—the same window idea as `.rolling()` in Pandas, but explicit for learning.

### Concept

For index `i`, consider samples from `max(0, i - k + 1)` through `i` inclusive. Average those entries. Edge windows are shorter until `i >= k - 1`. This is \(O(n \cdot k)\) if implemented naïvely; for CS 101 and small `k` that is fine.

```python
def running_mean(series, k):
    out = []
    for i in range(len(series)):
        start = max(0, i - k + 1)
        window = series[start : i + 1]
        out.append(sum(window) / len(window))
    return out


oat = [40, 41, 39, 38, 42, 43]
print(running_mean(oat, 3))
```

### Why this matters

Smoothing SAT or static pressure before thresholds reduces false trips. Understanding windows helps you read FDD code that uses **rolling means**, **max over last N minutes**, etc.—even when a library implements them efficiently.

### Mini examples

- **Trailing max:** max valve command in last `k` samples (use inner loop or Python `max()` on slice).
- Drop `None` in window: build `clean = [x for x in window if x is not None]` before averaging.
- Compare `k=3` vs `k=12` on the same synthetic noisy list and describe delay vs smoothness tradeoff.

### Micro exercises

1. Write `rolling_max(series, k)` returning a list of same length as `series`.
2. Given parallel `timestamps` and `values`, ensure windows never cross a **gap** > `gap_sec` (reset window after gap)—pseudocode first, then code if time permits.
3. For `k=5`, how many multiplications/additions does the naive algorithm do for \(n=1000\)? (Big-O reasoning only.)

### Key takeaway

Sliding windows = **controlled memory** of recent behavior. Implementing them with slices builds intuition for **time-series FDD** without importing a dataframe stack.
