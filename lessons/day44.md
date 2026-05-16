## Day 44 — GL36 central plant: chiller enable from AHU valve requests

### Goal

Implement **ASHRAE Guideline 36 §5.18.15.2** style **chiller plant enable**: count how many **AHU chilled-water valve** positions are “requesting” cooling, enforce **minimum ON/OFF** times, and output **`chillerEnableCommand`**. Python follows the Java block that watches up to **20** `ahuClgVlvN` inputs.

### Concept — per-AHU latch

For each wired AHU valve `%`:

- If valve **≥ request threshold** (default **95%**) → latch **requesting = 1**
- If valve **≤ disable threshold** (default **10%**) → latch **requesting = 0**
- Between thresholds → **hold** last state (hysteresis)

**Enable plant** when:

- `totalRequests >= numOfAhusReq` (default **2**), **and**
- plant has been **OFF** at least **`minOffTimeMinutes`**

**Disable plant** when:

- `totalRequests == 0`, **and**
- plant has been **ON** at least **`minOnTimeMinutes`**

Tick every **10 s** (same as Niagara).

### Python port

```python
class ChillerPlantEnable:
    DIS_THRESH = 10.0
    EXEC_SEC = 10

    def __init__(self, req_thresh=95.0, num_required=2, min_on_min=10, min_off_min=10):
        self.req_thresh = max(req_thresh, 30.0)
        self.num_required = max(int(num_required), 1)
        self.min_on_sec = int(max(min_on_min, 10) * 60)
        self.min_off_sec = int(max(min_off_min, 10) * 60)
        self.ahu_states = [0] * 20
        self.running = False
        self.on_sec = 0
        self.off_sec = 0

    def tick(self, valve_pcts):
        # valve_pcts: list of float or None (None = unwired)
        total = 0
        wired = 0
        for i in range(20):
            v = valve_pcts[i] if i < len(valve_pcts) else None
            if v is None:
                self.ahu_states[i] = 0
                continue
            wired += 1
            if v >= self.req_thresh:
                self.ahu_states[i] = 1
            elif v <= self.DIS_THRESH:
                self.ahu_states[i] = 0
            total += self.ahu_states[i]

        if wired == 0:
            self.running = False
            self.on_sec = self.off_sec = 0
            return False, total, "no AHU inputs wired"

        if not self.running:
            self.on_sec = 0
            self.off_sec += self.EXEC_SEC
            if total >= self.num_required and self.off_sec >= self.min_off_sec:
                self.running = True
                self.off_sec = 0
                return True, total, "START"
            return False, total, f"OFF waiting off={self.off_sec}s"
        else:
            self.off_sec = 0
            self.on_sec += self.EXEC_SEC
            if total == 0 and self.on_sec >= self.min_on_sec:
                self.running = False
                self.on_sec = 0
                return False, total, "STOP"
            return True, total, f"ON on={self.on_sec}s"


# demo: three AHUs ramp valves
plant = ChillerPlantEnable(num_required=2)
valves = [None] * 20
for step in range(30):
    if step > 5:
        valves[0] = 98.0
    if step > 8:
        valves[1] = 97.0
    if step > 20:
        valves[0] = valves[1] = 5.0
    en, n, msg = plant.tick(valves)
    print(f"step={step} enable={en} R={n} {msg}")
```

### Micro exercises

1. Graph **`enable`** vs time when one AHU hits **96%** early and a second joins later.
2. What happens if **`numOfAhusReq = 1`** but **`minOffMin = 30`**?
3. List BACnet points you would trend in the field to prove the plant is not short-cycling.

### See also

- **Day 45** — AHU **SAT error** request counter (feeds HW/CHW resets).
- **Day 47** — CHW **Trim & Respond** (plant capacity loop).

### Key takeaway

**Plant enable** is **counting + hysteresis + minimum run times**—not instantaneous valve position—so chillers do not chatter when one AHU blips to full cooling.
