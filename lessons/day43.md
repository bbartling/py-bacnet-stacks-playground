## Day 43 — GL36 AHU supply air temperature (SAT) Trim & Respond

### Goal

Implement **SAT reset** with **Trim & Respond** plus an **outdoor-air (OAT) reset curve**: maintain an internal **`tMax`** band, trim/respond based on summed **cooling requests `R`**, then **interpolate** discharge SAT setpoint between OAT limits. Python mirrors the Java block that uses **`SP0` / `SPmin` / `SPmax`**, **`outsideAirTemp`**, and **`totalRequests`**.

### Concept — signs matter

For **cooling SAT**, you usually want **higher SAT** when load is low (trim **up**) and **lower SAT** when zones need cooling (respond **down**):

| Action | Typical SPtrim | Typical SPres |
|--------|----------------|---------------|
| **Trim** (few requests) | **+0.2 °F** per step | — |
| **Respond** (many requests) | — | **−0.3 °F × (R − I)**, capped |

**SP₀** often equals **`SPmax`** (warmest allowable SAT at start). **`tMaxState`** tracks the reset ceiling before the OAT curve shapes the final **`dischargeAirTempSp`**.

### OAT interpolation (diamond curve)

Given **`oat`**, **`oatMin`**, **`oatMax`**, and current **`tMax`**:

```python
def interpolate(oat, oat_min, t_at_min, oat_max, t_at_max, spmin, spmax):
    if oat <= oat_min:
        y = t_at_min
    elif oat >= oat_max:
        y = t_at_max
    else:
        slope = (t_at_max - t_at_min) / (oat_max - oat_min)
        y = t_at_min + slope * (oat - oat_min)
    if y < spmin:
        return spmin
    if y > spmax:
        return spmax
    return y
```

### Python port (°F, simplified state machine)

```python
import time


def clamp(v, lo, hi):
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


def interpolate(oat, oat_min, t_at_min, oat_max, t_at_max, spmin, spmax):
    if oat <= oat_min:
        y = t_at_min
    elif oat >= oat_max:
        y = t_at_max
    else:
        slope = (t_at_max - t_at_min) / (oat_max - oat_min)
        y = t_at_min + slope * (oat - oat_min)
    return clamp(y, spmin, spmax)


class SatTrimRespond:
    def __init__(self):
        self.spmin = 55.0
        self.spmax = 70.0
        self.oat_min = 60.0
        self.oat_max = 70.0
        self.td_sec = 10 * 60
        self.t_sec = 2 * 60
        self.ignore = 2.0
        self.trim = 0.2
        self.resp = -0.3
        self.resp_max = -1.0
        self.t_max = 70.0
        self.last_step_ms = 0
        self.fan_on_since_ms = 0
        self.last_fan = False

    def tick(self, now_ms, fan_run, oat, total_requests, requests_ok=True):
        sp0 = clamp(self.spmax, self.spmin, self.spmax)

        if not fan_run:
            self.t_max = sp0
            self.last_fan = False
            self.fan_on_since_ms = 0
            sp = self._sat_sp(oat)
            return sp, "fan OFF -> SP0/tMax reset"

        if not self.last_fan:
            self.fan_on_since_ms = now_ms
            self.last_fan = True
            self.t_max = sp0
            return self._sat_sp(oat), "fan ON -> hold during Td"

        if (now_ms - self.fan_on_since_ms) // 1000 < self.td_sec:
            return self._sat_sp(oat), "startup delay"

        if self.last_step_ms and (now_ms - self.last_step_ms) // 1000 < self.t_sec:
            return self._sat_sp(oat), "between T steps"

        if not requests_ok:
            self.t_max = sp0
            self.last_step_ms = 0
            self.fan_on_since_ms = now_ms
            return sp0, "RESTART bad R -> SP0"

        r = total_requests
        if r <= self.ignore:
            self.t_max = clamp(self.t_max + self.trim, self.spmin, self.spmax)
            action = "TRIM tMax up"
        else:
            amount = max(self.resp * (r - self.ignore), self.resp_max)
            self.t_max = clamp(self.t_max + amount, self.spmin, self.spmax)
            action = f"RESPOND tMax {amount:+.2f}"

        self.last_step_ms = now_ms
        sp = self._sat_sp(oat)
        return sp, f"{action} R={r} tMax={self.t_max:.1f} SATsp={sp:.1f}"

    def _sat_sp(self, oat):
        return interpolate(oat, self.oat_min, self.t_max, self.oat_max,
                           self.spmin, self.spmin, self.spmax)


# demo
ctl = SatTrimRespond()
t0 = int(time.time() * 1000)
for m in range(25):
    fan = m >= 2
    oat = 65.0
    r = 0 if m < 12 else 6
    sp, msg = ctl.tick(t0 + m * 60_000, fan, oat, r)
    print(f"m={m:02d} R={r} SATsp={sp:.1f}  {msg}")
```

### Micro exercises

1. Sweep **`oat`** from **55 → 75** with fixed **`tMax = 65`** and print the SAT setpoint curve.
2. Explain why **`tMax`** is trimmed **up** but **`SPres`** is **negative** (cooling direction).
3. Pair with **Day 42**: when both duct static and SAT reset run, which loop reacts faster to a single hot zone?

### See also

- **Day 41** — per-zone **cooling** requests summed into **`R`**.
- **Day 45** — central plant reads **AHU-level** request counters.

### Key takeaway

**SAT Trim & Respond** separates **load-driven ceiling (`tMax`)** from **weather-shaped delivery (OAT curve)**—two layers that together keep coils efficient and zones satisfied.
