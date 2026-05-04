## Day 30 – Counting & frequency tables (fault codes, equipment types)

### Goal

Build a **frequency table** with a dictionary: how often each key appears. Use **HVAC / BAS** keys (fault codes, object types, priority buckets).

### Concept

For each item: if seen before, increment count; else set count to 1. This is the logic behind `collections.Counter`—worth using in production—but implementing once cements **hash map + loop** thinking.

### How to use it

```python
def count_occurrences(items):
    counts = {}
    for item in items:
        counts[item] = counts.get(item, 0) + 1
    return counts


fault_codes = ["F01", "F03", "F01", "F01", "F02", "F03"]
print(count_occurrences(fault_codes))  # {'F01': 3, 'F03': 2, 'F02': 1}
```

### Why this matters

After a week of trend review you might ask: **how many times** did `high_supply_temp` fire? How many devices per **equipment template** in an export? Frequency tables feed dashboards and help tune thresholds (“this nuisance alarm dominates”).

### Mini examples

- Count **normalized** strings: `code.strip().upper()` before using as key.
- Count bins: map each float to a string bucket `"<60"`, `"60-70"`, `">70"` for histogram-style summaries.
- Given `list[tuple[str, int]]` of `(device_type, instance)`, count devices per `device_type`.

### Micro exercises

1. Write `count_words(sentence)` splitting on whitespace; ignore empty strings.
2. From a list of `(point_name, alarm_state)` where `alarm_state` is `"active"` or `"normal"`, count how many points are **currently** active (each name appears once per snapshot—still good counting practice).
3. Return the **most common** key from a non-empty counts dict (linear scan over `items()`).

### Key takeaway

Counting with dicts is a core “summarize this log” algorithm. It pairs naturally with **fault analytics** and inventory views.
