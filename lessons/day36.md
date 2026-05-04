## Day 36 – Deadbands, envelopes, and “mixed air in band”

### Goal

Avoid **chattering** alarms with **deadbands** and test **envelope** relationships inspired by mixed-air sanity checks (ASHRAE Guideline 36 / open-fdd cookbook **Rule B / Rule C** style—high level only).

### Concept

- **Deadband:** require `x > hi + d` to turn on, `x < hi - d` to turn off (hysteresis). Two thresholds beat one for stable outputs.
- **Envelope:** for mixing sections, **MAT** should usually lie between **OAT** and **RAT** (plus tolerances). Outside the band ⇒ possible sensor or mixing issue—**not** a definitive diagnosis, just algorithmic detection.

Single-timestep checks (plain Python):

```python
def mat_below_band(mat, oat, rat, tol):
    lower_bound = min(oat, rat) - tol
    return mat < lower_bound


def mat_above_band(mat, oat, rat, tol):
    upper_bound = max(oat, rat) + tol
    return mat > upper_bound
```

Combine with fan proof if you like: `fault = mat_below_band(...) and fan_on`.

### Why this matters

Real FDD separates **physics-informed expectations** from **threshold noise**. Deadbands save service tickets; envelope tests encode rudimentary **thermodynamic consistency** without solving full psychrometrics in this mini-course.

### Mini examples

- Implement `with_deadband(x, on_hi, off_hi, state_was_on)` returning new bool state for a high-temp alarm.
- “Two of three” voting: three redundant zone sensors; flag if two disagree by more than `delta`.
- Document tolerances (`tol`) as **parameters**, not magic numbers in the middle of code.

### Micro exercises

1. Write `in_band(mat, oat, rat, tol)` returning `True` if `min(oat, rat) - tol <= mat <= max(oat, rat) + tol`.
2. Add `fan_cmd > 0.01` to gate `mat_below_band` (fan must be running).
3. Explain why envelope tests **alone** cannot distinguish a bad MAT sensor from a real economizer fault.

### Key takeaway

HVAC-friendly algorithms combine **comparisons**, **tolerances**, and **gating**—patterns you will recognize in industrial FDD YAML, even when a library evaluates them for you.
