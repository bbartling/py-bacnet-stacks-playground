## Day 40 – Capstone: parallel lists + simple fault timeline (still no Pandas)

### Goal

Combine the arc: **aligned sequences** (timestamps + signals), **Boolean rules**, optional **smoothing**, and a tiny **post-processing** pass to build a **fault timeline** (list of bools or `0/1`). This mimics one column an AFDD tool might produce—implemented with lists and loops only.

### Concept

Assume equal-length lists:

- `t_sec` — time from start in seconds (monotonic)
- `sat`, `sat_sp`, `fan_cmd` — floats you trust are aligned sample-by-sample

Pipeline sketch:

1. Optional: `sat_smooth = running_mean(sat, k=3)` (Day 37).
2. Rule: `high_sat = s > sat_sp + 2.0` for each index `i` (Day 35–36 style).
3. Optional gate: `fan_on = fan_cmd[i] > 0.01`.
4. `fault[i] = high_sat[i] and fan_on`.

```python
def zip_fault_timeline(sat, sat_sp, fan_cmd, margin, fan_eps):
    fault = []
    for i in range(len(sat)):
        hi = sat[i] > sat_sp[i] + margin
        fan_on = fan_cmd[i] > fan_eps
        fault.append(hi and fan_on)
    return fault


def count_true(flags):
    n = 0
    for f in flags:
        if f:
            n += 1
    return n
```

### Why this matters

Real stacks add **column maps**, **ontology labels** (Brick/Haystack), **schedules**, and **vectorized** evaluation—but the **logical skeleton** is what you just wrote. Understanding the skeleton makes open-fdd-style YAML readable instead of magic.

### Mini examples

- Append `fault_id` strings instead of bools: `"NONE"` vs `"HIGH_SAT"`.
- Count **consecutive** `True` run length after index `i` (simple forward scan).
- Export CSV lines with `zip(t_sec, sat, fault)` and `",".join(...)` (Day 32).

### Micro exercises

1. Given `fault` bools, return a list of `(start_index, end_index)` for each contiguous `True` run (linear scan; one pass).
2. Add `occupied[i]` bool list; require `occupied[i]` for fault to trigger.
3. Write five bullet **test cases** (inputs → expected fault pattern) for your rule.

### Course fit — self-evaluation

| Criterion | How this arc behaves |
|-----------|----------------------|
| CS 101 appropriate? | Yes: loops, conditionals, functions, lists, sorting, dict counting, simple numerics. |
| Avoids advanced algos? | No shortest-path, no DP, no recursive backtracking required. |
| HVAC + FDD relevant? | Yes: thresholds, envelopes, windows, R–C + Euler tie domain to code. |
| open-fdd alignment? | Conceptual Boolean + cookbook patterns; **not** a Pandas/RuleRunner tutorial. |
| Daily size | Each day targets **one** skill; capstone stitches them. |

### Where topics moved

Earlier versions of Days **35–40** included a weather BACnet final project, mini BACnet devices, Wireshark, **systemd**, and **Docker**—valuable **operations** skills. Those are **not deleted from the repo history**; they can live in a separate “ops week” or be revived beside this algorithms track. Ask your instructor which track you are following.

### Key takeaway

**Algorithms + physics-lite models + Boolean FDD** form a coherent mini-course: you can explain, test, and ship small Python tools before adopting heavier frameworks.
