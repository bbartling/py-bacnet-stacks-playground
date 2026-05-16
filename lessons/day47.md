## Day 47 — GL36 central plant: chilled water Trim & Respond (DP + CHWST)

### Goal

Implement **one 0–100% Trim & Respond loop** that maps into **two physical resets** per **ASHRAE Guideline 36 §5.20.5.2**:

1. **Chilled water differential pressure (DP)** — optimize pumps first (**0–50%** of loop)
2. **CHW supply temperature (CHWST)** — optimize chillers second (**50–100%** of loop)

> Lab note: treat this as **theory + Python sketch**; field tuning may differ. The Java reference in n4-hvac-optimization-blocks is marked **not fully tested** in production docs—use for learning the **shape** of the reset.

### Concept — loop starts at 100%

- **SP₀ = 100%** means **max DP** and **coldest CHWST** (full plant capability).
- When **`effectiveR = max(0, totalRequests − I)`** is zero → **trim** loop down (negative **`spTrim`**, e.g. **−2%** per step).
- When **`effectiveR > 0`** → **respond** loop up, capped by **`spRespondMax`**.

After each step, map **`loopVal`** to outputs:

| Loop % | DP | CHWST |
|--------|----|-------|
| 0% | DP min | Warmest |
| 50% | DP max | Warmest |
| 100% | DP max | Coldest |

### Python port

```python
def clamp(v, lo, hi):
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


def map_chw_loop(loop_pct, dp_min, dp_max, st_min, st_max):
    loop_pct = clamp(loop_pct, 0.0, 100.0)
    if loop_pct <= 50.0:
        r = loop_pct / 50.0
        dp = dp_min + r * (dp_max - dp_min)
        st = st_max
        stage = "stage1 DP"
    else:
        r = (loop_pct - 50.0) / 50.0
        dp = dp_max
        st = st_max - r * (st_max - st_min)
        stage = "stage2 CHWST"
    return dp, st, stage


class ChwPlantTrimRespond:
    def __init__(self):
        self.loop = 100.0
        self.enabled_since_ms = 0
        self.last_step_ms = 0
        self.was_enabled = False

    def tick(self, now_ms, enable, total_req, td_min=15, step_min=5,
             sp_trim=-2.0, sp_res=3.0, sp_res_max=7.0, ignore=0.0):
        if not enable:
            self.loop = 100.0
            self.was_enabled = False
            dp, st, stg = map_chw_loop(self.loop, 10, 25, 42, 55)
            return self.loop, dp, st, "disabled"

        if not self.was_enabled:
            self.enabled_since_ms = now_ms
            self.was_enabled = True
            self.loop = 100.0
            dp, st, _ = map_chw_loop(self.loop, 10, 25, 42, 55)
            return self.loop, dp, st, "init SP0"

        if (now_ms - self.enabled_since_ms) < td_min * 60_000:
            dp, st, _ = map_chw_loop(self.loop, 10, 25, 42, 55)
            return self.loop, dp, st, "startup delay"

        if self.last_step_ms and (now_ms - self.last_step_ms) < step_min * 60_000:
            dp, st, stg = map_chw_loop(self.loop, 10, 25, 42, 55)
            return self.loop, dp, st, "hold"

        eff = max(0.0, total_req - ignore)
        if eff > 0:
            self.loop = clamp(self.loop + min(eff * sp_res, sp_res_max), 0, 100)
            act = "respond"
        else:
            self.loop = clamp(self.loop + sp_trim, 0, 100)
            act = "trim"

        self.last_step_ms = now_ms
        dp, st, stg = map_chw_loop(self.loop, 10, 25, 42, 55)
        return self.loop, dp, st, f"{act} R={total_req} {stg}"
```

### Micro exercises

1. Print **`dp, st`** for **`loop = 0, 25, 50, 75, 100`**.
2. Explain in one paragraph why **50%** is not “half the AHUs requesting.”
3. Draw a block diagram: **VAV → AHU SAT/pressure → plant R → CHW loop → DP + CHWST**.

### See also

- **Days 41–43** — air side.
- **Days 44–46** — plant enable, AHU plant requests, HWST.
- **Day 48** — Brick / RDF graph track begins.

### Key takeaway

**Central plant cooling** can be one **capacity slider** (0–100%) that stages **hydraulic** then **thermal** efficiency—Trim & Respond finds the lowest stable setting before zones complain.
