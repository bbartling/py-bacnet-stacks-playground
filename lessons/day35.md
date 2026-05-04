## Day 35 – Fault detection as Boolean logic (no Pandas)

### Goal

Express **simple AFDD-style rules** the way rule engines do conceptually: comparisons, **AND / OR / NOT**, thresholds from parameters. Use **plain Python** on scalars or aligned lists—**no Pandas**, no `eval` on strings—mirroring the *spirit* of open-fdd **expression** rules (see `open-fdd/docs/expression_rule_cookbook.md`) while staying CS-101 sized.

### Concept

A **fault flag** is often “expression is True.” Example pattern from cookbook thinking (GL36-inspired duct static idea, simplified):

- Inputs: `duct_static`, `static_setpoint`, `fan_cmd_frac` (0–1 or 0–100—**pick one convention** and document it).
- Params: margins (numbers), high-drive fraction.
- Logic (read as math, not YAML):

\[
\text{fault} = (\text{static} < \text{setpoint} - m) \land (\text{fan\_cmd} \ge f_{\text{hi}} - \epsilon)
\]

In Python for **one timestep**:

```python
def rule_duct_static_low(static, setpoint, fan_cmd, sp_margin, drv_hi, drv_near_hi):
    low_static = static < setpoint - sp_margin
    fan_near_max = fan_cmd >= drv_hi - drv_near_hi
    return low_static and fan_near_max
```

### Why this matters

Production tools (e.g. **open-fdd**) add schedules, column maps, and vectorized `numpy`/`pandas`—but the **underlying idea** is still Boolean algebra on aligned signals. Writing rules explicitly trains you to **normalize units**, **name variables**, and **avoid contradictions**.

### Mini examples

- Add **occupancy gating**: `fault = raw_fault and occupied` where `occupied` is a bool you pass in.
- OR two independent symptoms: `leak_suspect = low_static or unexpected_flow`.
- NOT: `equipment_on = not (fan_cmd < 0.01)`.

### Micro exercises

1. Implement `economizer_cooling_when_cold(oat, sat, sat_sp, oat_high_limit)` returning `True` when `oat < oat_high_limit` and `sat < sat_sp - 2.0` (toy rule—tune later).
2. Write `weather_band_ok(oat, low_f, high_f)` and combine with another flag using `and`.
3. List three ways **bad units** (0–1 vs 0–100 commands) make Boolean rules silently wrong.

### See also

- **open-fdd** cookbook (full engine uses Pandas/NumPy): clone **open-fdd** and read `docs/expression_rule_cookbook.md` (path depends on your machine).
- BACnet mini servers / Wireshark / deployment topics live in other weeks of this repo’s lesson set or `README.md`—this week stays focused on **algorithms + light FDD math**.

### Key takeaway

Fault detection at its simplest is **comparison + Boolean structure**. Master that on scalars before trusting a framework to do it across whole DataFrames.
