## Day 33 – Membership (`in`) and index search

### Goal

Use **`in`** for quick presence checks and relate it to **linear search with an index** when you need position or alignment with parallel lists.

### Concept

For lists, `x in lst` is implemented by scanning (same asymptotic cost as linear search). Strings: `sub in s` checks substring. When you also need **where** something occurred, keep the explicit `for i in range(len(...))` pattern from Day 28.

### How to use it

```python
def equipment_allowed(device_tag, approved_list):
    return device_tag in approved_list


def linear_search(lst, target):
    for i in range(len(lst)):
        if lst[i] == target:
            return i
    return -1


points = ["OAT", "RAT", "MAT", "SAT"]
print("MAT" in points, linear_search(points, "SAT"))
```

### Why this matters

You might gate logic: **only evaluate AFDD rules** if required sensors exist in today’s export (`"SAT" in header_names`). Or verify an operator-entered equipment id is in an **allow-list** before running a simulation.

### Mini examples

- `if fan_cmd > 0.01 and "SAT" in available_sensors:` as a conceptual guard (booleans + membership).
- Search a list of **substrings**: first index where `any(name in full for ...)`—keep it simple; nested loop is fine at 101 level.
- Parallel lists: `names[i]` corresponds to `values[i]`; find `i` where `names[i] == target`, then read `values[i]`.

### Micro exercises

1. Check whether substring `"fan"` appears in `"supply_fan_speed_command"` (case insensitive).
2. Write `index_of_first_true(bools)` returning the first index of `True`, or `-1`.
3. Given `tags` and `values` of equal length, return the value for the first tag equal to `"SAT"`, or `None`.

### Key takeaway

`in` answers “exists?”; a small loop answers “where?”—both show up constantly in **BAS data prep** and **rule gating**.
