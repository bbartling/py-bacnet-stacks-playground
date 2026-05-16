## Day 41 — GL36 Trim & Respond vocabulary + VAV zone requests (0–3)

### Goal

Learn **ASHRAE Guideline 36 (GL36) Trim & Respond** naming (`SP₀`, `R`, `SPtrim`, `SPres`, …) and implement a **VAV box zone request generator** in plain Python: integer outputs **0–3** for **cooling SAT requests** and **duct static pressure requests**, matching the Niagara/Java logic in the [n4-hvac-optimization-blocks](https://github.com/bbartling/n4-hvac-optimization-blocks) repo.

### Concept — Table 5.1.14.3 variables

| Variable | Meaning |
|----------|---------|
| **SP₀** | Initial setpoint before reset |
| **SPmin / SPmax** | Clamp limits |
| **Td** | Startup delay |
| **T** | Trim/respond interval |
| **I** | Ignored requests (often **0** for critical zones) |
| **R** | Sum of zone requests (fed to AHU reset) |
| **SPtrim** | Trim step (reduce load when few requests) |
| **SPres** | Respond step per effective request |
| **SPres-max** | Cap on one respond move |

At the **VAV**, you do not trim a plant setpoint yet—you **count how hard the zone is working** and export **`vavCoolRequests`** and **`vavPressureRequests`** (each **0–3**).

### Cooling requests (temperature ladder)

After a **1-minute suppression** window from start:

- **3** if zone temp ≥ setpoint + **3 °C** (or +**5 °F** imperial) for **2 minutes**
- **2** if zone temp ≥ setpoint + **2 °C** (or +**3 °F**) for **2 minutes**
- **1** if cooling loop (zone demand) **> 95%** until it drops **< 85%** (hysteresis)
- **0** otherwise

### Pressure requests (damper + flow ladder)

- **3** if flow **< 50%** of setpoint **and** damper **≥ 95%** for **1 minute**
- **2** if flow **< 70%** of setpoint **and** damper **≥ 95%** for **1 minute**
- **1** if damper **≥ 95%** until damper **< 85%**
- **0** otherwise

Execute every **10 s** (same as a Niagara `Clock.schedule` tick).

### Python port (stateful class)

```python
def clamp_int(v, lo=0, hi=3):
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


def is_valid(x, lo, hi):
    return lo <= x <= hi


class Gl36VavRequestCounter:
  EXEC_SEC = 10

  def __init__(self, use_imperial=False):
    self.use_imperial = use_imperial
    self.press_high_t = 0.0
    self.press_med_t = 0.0
    self.last_press_req = 0
    self.temp_high_t = 0.0
    self.temp_med_t = 0.0
    self.temp_suppress_t = 0.0
    self.last_temp_req = 0

  def tick(self, zone_temp, zone_sp, zone_demand_pct,
           vav_flow, vav_flow_sp, damper_pct):
    self.temp_suppress_t = min(self.temp_suppress_t + self.EXEC_SEC, 60)

    press_req = self._pressure_req(vav_flow, vav_flow_sp, damper_pct)
    cool_req = self._temp_req(zone_temp, zone_sp, zone_demand_pct)

    self.last_press_req = press_req
    self.last_temp_req = cool_req
    return clamp_int(cool_req), clamp_int(press_req)

  def _pressure_req(self, flow, sp, damper):
    if not (is_valid(damper, -10, 110) and is_valid(flow, -10, 1e5) and is_valid(sp, -10, 1e5)):
      self.press_high_t = self.press_med_t = 0.0
      return 0
    if sp <= 0:
      return 0
    ratio = flow / sp
    if ratio < 0.50 and damper >= 95.0:
      self.press_high_t += self.EXEC_SEC
    else:
      self.press_high_t = 0.0
    if self.press_high_t >= 60:
      self.press_med_t = 0.0
      return 3
    if ratio < 0.70 and damper >= 95.0:
      self.press_med_t += self.EXEC_SEC
    else:
      self.press_med_t = 0.0
    if self.press_med_t >= 60:
      return 2
    if damper >= 95.0:
      return 1
    if self.last_press_req == 1 and damper >= 85.0:
      return 1
    return 0

  def _temp_req(self, tz, sp, demand):
    if self.use_imperial:
      hi, med, tmin, tmax = 5.0, 3.0, 32.0, 125.0
    else:
      hi, med, tmin, tmax = 3.0, 2.0, 0.0, 50.0
    if not (is_valid(tz, tmin, tmax) and is_valid(sp, tmin, tmax) and is_valid(demand, -200, 200)):
      self.temp_high_t = self.temp_med_t = 0.0
      return 0
    diff = tz - sp
    if self.temp_suppress_t >= 60:
      if diff >= hi:
        self.temp_high_t += self.EXEC_SEC
        self.temp_med_t = 0.0
      elif diff >= med:
        self.temp_med_t += self.EXEC_SEC
        self.temp_high_t = 0.0
      else:
        self.temp_high_t = self.temp_med_t = 0.0
      if self.temp_high_t >= 120:
        return 3
      if self.temp_med_t >= 120:
        return 2
    if demand > 95.0:
      return 1
    if self.last_temp_req == 1 and demand >= 85.0:
      return 1
    return 0


# --- toy walk ---
vav = Gl36VavRequestCounter(use_imperial=True)
for _ in range(20):  # 200 s simulated
  cool, press = vav.tick(zone_temp=76.0, zone_sp=72.0, zone_demand_pct=40.0,
                         vav_flow=200.0, vav_flow_sp=800.0, damper_pct=98.0)
print("cool=", cool, "press=", press)
```

### BACnet / supervisory angle

On a real job, **`vavCoolRequests`** might be a BACnet **AV** or internal proxy point; the **AHU** sums **`R`** from many VAVs and feeds **Day 42–43** reset blocks. Your Python lesson is the **same math** Niagara runs in a `ProgramObject`.

### Micro exercises

1. Log **`cool, press`** every tick to a CSV: `time_sec,cool_req,press_req`.
2. Force **invalid** `zone_temp` (e.g. `-999`) and confirm both requests return **0** (fail-safe).
3. Sketch how **four VAVs** with requests `[0,1,3,2]` produce **`R = 6`** at the AHU.

### See also

- [GL36 Trim & Respond README](https://github.com/bbartling/n4-hvac-optimization-blocks) (Java Niagara source for this block).
- **Day 42** — AHU duct static **Trim & Respond** consumes summed pressure requests.

### Key takeaway

**GL36 supervisory control** starts at the **terminal**: zones vote with **0–3 request integers**; AHUs and central plant **aggregate `R`** and move setpoints in **trim** or **respond** steps.
