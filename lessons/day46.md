## Day 46 — GL36 central plant: hot water supply temperature Trim & Respond

### Goal

Reset **hot water supply temperature (HWST)** from aggregated **heating requests**: **trim down** when demand is low, **respond up** when **`effectiveR = max(0, R − I)`** is positive. Python mirrors the boiler HWST block with **`enable`**, **`plantProvenOn`**, and fail-safe **SP₀** on bad data.

### Concept

| Condition | Action |
|-----------|--------|
| `enable` false or plant not proven ON | Hold **SP₀** (safe / design max HWST) |
| `effectiveR > 0` | **Respond ↑** by `min(effectiveR × spRespond, spRespondMax)` |
| else | **Trim ↓** by `spTrim` (negative increment) |

Clamp every step: **`spMin ≤ HWST ≤ spMax`**.

Recommended for central plant: **`ignoredReq = 0`** so every heating vote counts.

### Python port

```python
class HwstTrimRespond:
    def __init__(self, sp0=150.0, spmin=90.0, spmax=180.0,
                 step_min=5, sp_trim=-2.0, sp_respond=3.0, sp_respond_max=7.0, ignore=0.0):
        self.sp0 = sp0
        self.spmin = spmin
        self.spmax = spmax
        self.step_ms = int(step_min * 60_000)
        self.sp_trim = sp_trim
        self.sp_respond = sp_respond
        self.sp_respond_max = sp_respond_max
        self.ignore = ignore
        self.hwst = sp0
        self.last_step_ms = 0

    def tick(self, now_ms, enable, plant_on, total_requests, req_ok=True):
        active = enable and plant_on
        if not active:
            self.hwst = self.sp0
            self.last_step_ms = 0
            return self.hwst, 0.0, "inactive -> SP0"

        if not req_ok:
            self.hwst = self.sp0
            self.last_step_ms = 0
            return self.hwst, 0.0, "FAULT -> SP0"

        if self.last_step_ms and (now_ms - self.last_step_ms) < self.step_ms:
            eff = max(0.0, total_requests - self.ignore)
            return self.hwst, eff, "hold"

        eff = max(0.0, total_requests - self.ignore)
        if eff > 0:
            bump = min(eff * self.sp_respond, self.sp_respond_max)
            self.hwst = clamp(self.hwst + bump, self.spmin, self.spmax)
            action = f"respond +{bump:.1f}"
        else:
            self.hwst = clamp(self.hwst + self.sp_trim, self.spmin, self.spmax)
            action = f"trim {self.sp_trim:.1f}"

        self.last_step_ms = now_ms
        return self.hwst, eff, action


def clamp(v, lo, hi):
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v
```

### Micro exercises

1. Run **`R = [0,0,0,4,4,0]`** every 5 minutes and plot HWST.
2. Explain fail-safe behavior when **`totalHwResetReq`** goes NULL mid-run.
3. Contrast **HWST trim direction** with **SAT trim direction** (Day 43).

### See also

- **Day 45** — produces **`R`** from AHU heating ladders.
- **Day 47** — dual-output **CHW** reset (DP + CHWST).

### Key takeaway

**HWST T&R** keeps plant water as cool as possible until enough **heating requests** prove the building needs more capacity.
