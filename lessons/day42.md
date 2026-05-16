## Day 42 — GL36 AHU duct static pressure Trim & Respond

### Goal

Implement **ASHRAE Guideline 36 §5.1.14.4** — **duct static pressure reset** on the **supply fan**: lower static when few VAVs need air (**trim**), raise it when many dampers are starved (**respond**). Port the Java `ProgramObject` pattern to Python with the same **fan ON → startup delay → periodic T&R** state machine.

### Concept — what moves

| G36 | Typical imperial example | Role |
|-----|--------------------------|------|
| **SP₀** | 0.50 in w.c. | Initial / safe static SP |
| **SPmin** | 0.15 in w.c. | Floor |
| **SPmax** | 1.50 in w.c. | Ceiling |
| **Td** | 5 min | Hold SP₀ after fan proves ON |
| **T** | 2 min | Minutes between trim/respond steps |
| **I** | 2 | Ignore first *I* requests in respond math |
| **R** | Σ VAV pressure requests | From network / summed point |
| **SPtrim** | −0.04 in w.c. | Trim down when `R ≤ I` |
| **SPres** | +0.06 in w.c. per effective request | Respond up |
| **SPres-max** | +0.15 in w.c. cap per step | Limit one respond jump |

Core math each **T** minutes (when fan ON and delay met):

```text
if R <= I:   new_SP = clamp(current_SP + SPtrim, SPmin, SPmax)   # trim
else:        new_SP = clamp(current_SP + min(SPres*(R-I), SPres-max), SPmin, SPmax)
```

### Python port (imperial inches w.c.)

```python
import time


def clamp(v, lo, hi):
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


class DuctStaticTrimRespond:
    def __init__(self, sp0=0.50, spmin=0.15, spmax=1.50,
                 td_min=5, t_min=2, ignore=2,
                 sp_trim=-0.04, sp_res=0.06, sp_res_max=0.15):
        self.sp0 = sp0
        self.spmin = spmin
        self.spmax = spmax
        self.td_sec = int(td_min * 60)
        self.t_sec = int(t_min * 60)
        self.ignore = ignore
        self.sp_trim = sp_trim
        self.sp_res = sp_res
        self.sp_res_max = sp_res_max
        self.current_sp = sp0
        self.last_step_ms = 0
        self.fan_on_since_ms = 0
        self.last_fan = False

    def tick(self, now_ms, fan_run, total_requests, requests_ok=True):
        if not fan_run:
            self.current_sp = clamp(self.sp0, self.spmin, self.spmax)
            self.fan_on_since_ms = 0
            self.last_fan = False
            return self.current_sp, "fan OFF -> SP0"

        if not self.last_fan:
            self.fan_on_since_ms = now_ms
            self.last_fan = True
            self.current_sp = clamp(self.sp0, self.spmin, self.spmax)
            return self.current_sp, "fan ON edge -> SP0, start Td"

        if (now_ms - self.fan_on_since_ms) // 1000 < self.td_sec:
            self.current_sp = clamp(self.sp0, self.spmin, self.spmax)
            left = self.td_sec - (now_ms - self.fan_on_since_ms) // 1000
            return self.current_sp, f"startup delay {left}s"

        if self.last_step_ms and (now_ms - self.last_step_ms) // 1000 < self.t_sec:
            return self.current_sp, "hold between T steps"

        if not requests_ok:
            self.current_sp = clamp(self.sp0, self.spmin, self.spmax)
            self.last_step_ms = 0
            self.fan_on_since_ms = now_ms
            self.last_fan = True
            return self.current_sp, "RESTART: bad R -> SP0"

        r = total_requests
        if r <= self.ignore:
            self.current_sp = clamp(self.current_sp + self.sp_trim, self.spmin, self.spmax)
            action = "TRIM"
        else:
            bump = min(self.sp_res * (r - self.ignore), self.sp_res_max)
            self.current_sp = clamp(self.current_sp + bump, self.spmin, self.spmax)
            action = f"RESPOND +{bump:.3f}"

        self.last_step_ms = now_ms
        return self.current_sp, f"{action} R={r} SP={self.current_sp:.3f}"


# --- simulate 20 minutes ---
ctl = DuctStaticTrimRespond()
t0 = int(time.time() * 1000)
for minute in range(20):
    fan = minute >= 1
    r = 0 if minute < 8 else 5
    sp, msg = ctl.tick(t0 + minute * 60_000, fan, r)
    print(f"t={minute:02d}min R={r} SP={sp:.3f}  {msg}")
```

### Wiring mental model

```text
[VAV1..N pressure requests] --sum--> totalRequests --+
                                                      v
                                            [Duct static T&R] --> dischargeAirPressureSp
                                                      ^
                                            fanRunCmd (supply fan)
```

### Micro exercises

1. Plot **`current_sp`** vs time when **`R`** steps from **0 → 8 → 0** every 10 minutes.
2. Set **`I = 0`** and explain how respond behaves differently (more aggressive).
3. Compare **trim** on duct static (Day 42) vs **trim** on SAT (Day 43): which direction increases efficiency?

### See also

- **Day 41** — where **`R`** comes from (VAV pressure requests).
- **Day 43** — parallel **SAT** reset using **cooling** requests.

### Key takeaway

**Trim & Respond** is a **slow supervisory loop**: hold safe **SP₀** at startup, then nudge duct static **down** when the building is quiet and **up** when terminals prove they need more air.
