## Day 45 — GL36 central plant: AHU heating & cooling request counter

### Goal

Implement the **central plant AHU request counter** that turns **SAT error** and **valve saturation** into integer **0–3** levels for **cooling** and **heating**, used upstream of plant **Trim & Respond** loops. Matches the Java block with **parallel timers** (critical band also advances failing timer).

### Concept — error definitions

| Mode | Error (°F) |
|------|------------|
| Cooling | `SAT − SAT_setpoint` (too warm) |
| Heating | `SAT_setpoint − SAT` (too cold) |

| Level | Meaning | Trigger (summary) |
|------:|---------|-------------------|
| **3** | Critical | error ≥ **10°F** for **10 min** |
| **2** | Failing | error ≥ **5°F** for **5 min** |
| **1** | Saturated | valve latched **≥ 95%** until **< 85%** |
| **0** | Satisfied | none |

**Fan OFF** → reset timers, force **0** requests.

### Python port

```python
class AhuPlantRequestCounter:
    CRIT = 10.0
    FAIL = 5.0
    T_CRIT = 600
    T_FAIL = 300
    V_ON = 95.0
    V_OFF = 85.0

    def __init__(self):
        self.cool_crit = self.cool_fail = 0.0
        self.heat_crit = self.heat_fail = 0.0
        self.cool_latch = self.heat_latch = False

    def tick(self, step_sec, fan_on, sat, sat_sp, cool_vlv=None, heat_vlv=None):
        if not fan_on:
            self.cool_crit = self.cool_fail = 0.0
            self.heat_crit = self.heat_fail = 0.0
            self.cool_latch = self.heat_latch = False
            return 0, 0, "fan OFF"

        cool_req, cool_trace = self._mode(
            sat - sat_sp, cool_vlv,
            self.cool_crit, self.cool_fail, self.cool_latch,
        )
        self.cool_crit, self.cool_fail, self.cool_latch = cool_trace[1:]

        heat_req, heat_trace = self._mode(
            sat_sp - sat, heat_vlv,
            self.heat_crit, self.heat_fail, self.heat_latch,
        )
        self.heat_crit, self.heat_fail, self.heat_latch = heat_trace[1:]

        return cool_req, heat_req, f"cool={cool_req} heat={heat_req}"

    def _mode(self, err, vlv, t_crit, t_fail, latch):
        if vlv is None:
            return 0, (0.0, 0.0, latch)
        if err >= self.CRIT:
            t_crit += 10
            t_fail += 10
        elif err >= self.FAIL:
            t_crit = 0.0
            t_fail += 10
        else:
            t_crit = t_fail = 0.0
        if vlv >= self.V_ON:
            latch = True
        elif vlv < self.V_OFF:
            latch = False
        if t_crit >= self.T_CRIT:
            return 3, (t_crit, t_fail, latch)
        if t_fail >= self.T_FAIL:
            return 2, (t_crit, t_fail, latch)
        if latch:
            return 1, (t_crit, t_fail, latch)
        return 0, (t_crit, t_fail, latch)
```

*(In your full lesson file, pass `step_sec` into timer increments instead of hard-coded 10.)*

### Micro exercises

1. Simulate **SAT** stepping from **0°F error → 6°F → 11°F** and log request level vs time.
2. Why do **parallel timers** help when error drops from critical to failing?
3. Sum **three AHUs** with cooling requests `[1,3,2]` — what **`R`** do you feed **Day 47**?

### See also

- **Day 46** — **hot water** T&R uses summed **heating** requests.
- **Day 47** — **chilled water** T&R uses summed **cooling** requests.

### Key takeaway

Plant resets do not read room temps directly—they read **how hard each AHU is working** via a small integer **request ladder**.
