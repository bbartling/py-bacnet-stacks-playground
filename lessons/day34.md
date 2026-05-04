## Day 34 – Aggregates: sum, mean, median (one zone, one air handler)

### Goal

Compute **sum**, **mean**, and **median** with clear preconditions (empty list handling). Interpret results for **short HVAC samples** (15-minute SAT slice, weekly peak static).

### Concept

- **Mean:** `sum / n` (watch empty lists).
- **Median:** sort a **copy**, pick middle (average two middles if even length).
- **Min/max:** from Day 29; combine with sorted data for reporting.

### How to use it

```python
def mean(values):
    if not values:
        return None
    return sum(values) / len(values)


def median(values):
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    m = n // 2
    if n % 2:
        return s[m]
    return (s[m - 1] + s[m]) / 2


sat_f = [72.1, 71.9, 72.4, 72.0, 72.2]
print(round(mean(sat_f), 2), median(sat_f))
```

### Why this matters

Mean SAT over an interval smooths jitter; **median** resists single spikes when a sensor glitches. Same tools support **energy normalization** (mean kW) and **simple quality checks** (“median OAT overnight should match weather station roughly”).

### Mini examples

- Compute **mean absolute deviation** from setpoint: `mean(abs(t - sp) for t in zone_temps)`.
- Drop `None` readings before stats (small loop to build a clean list).
- Compare mean vs median on `[72.0, 72.1, 95.0, 72.0]` and comment which reflects “typical” better.

### Micro exercises

1. Write `stats_summary(values)` → dict with keys `min`, `max`, `mean`, `median` (or `None` if empty).
2. Given hourly OAT for 24 values, compute mean and median; which is less sensitive to one hour of bad data?
3. Explain why sorting is required for median but **not** for mean.

### Key takeaway

Aggregates compress time series into decisions humans (and rules) can digest—foundation for both **operations** and **lightweight FDD**.
