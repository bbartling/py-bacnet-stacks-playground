# Expression rule cookbook (Rule Lab)

How to write **browser Python** rules for DS18B20 telemetry. The backend only:

1. Loads MQTT rows from DynamoDB (`row`, `ts_ms`, `degF`, …)
2. Calls **`evaluate(row, cfg, prev_row, rows)`** once per row (or **`apply_faults(rows, cfg)`** if you define it)
3. Flags rows for the chart / FDD counts:
   - **`return True`** → flag **this row only**
   - **`return True, window_rows`** → flag **every row** in `window_rows` (retroactive lookback)
   - **`apply_faults(rows, cfg)`** → return `list[bool]` same length as `rows` (full control)

**Rolling avg on every row:** before each sweep, the engine adds a **time-based** trailing mean using `ts_ms`:

| Field | Meaning |
|-------|---------|
| `degF` | Instantaneous sample (same as MQTT) |
| `degF_raw` | Copy of instantaneous |
| `degF_rolling_avg` | Mean of all samples in the last **N minutes** (N = 1, 5, or 10) |
| `rolling_avg_minutes` | Window used (1, 5, or 10) |
| `rolling_window_ms` | `rolling_avg_minutes × 60_000` |
| `samples_in_avg` | How many MQTT rows fell in that time window |
| `sample_period_ms` | Median gap between samples (e.g. 11520 @ ~11.5 s) |

**Set the window:** Dashboard / Rule Lab dropdown (**1 / 5 / 10 min**), query `?rolling_avg_minutes=5` on `/api/readings`, test body `rolling_avg_minutes`, or rule config `rolling_avg_minutes` (per-rule on sweep).

**Rule Lab UI:** Each rule has a **Parameters (cfg)** panel — **+ Parameter** adds a row (edit key name + value), **−** removes it, **Add preset…** inserts known keys (`bounds_low_f`, `rolling_avg_minutes`, …). Keys are saved in DynamoDB with the rule and passed to `evaluate(row, cfg, …)`.

You still code **rolling_window debounce** yourself if you want sustained faults — see Recipe 2.

**Sandbox:** `print`, `math`, **`datetime`** / `timezone` (stdlib, always on), builtins, and optionally **`import numpy as np`** when Lambda has numpy (`/api/health` → `numpy_available: true`). `math`, `datetime`, and `np` are pre-injected in the sandbox.

---

## Recipe 1 — Out of bounds on rolling avg (uses pre-built row field)

**Config:** `bounds_low_f` = 65, `bounds_high_f` = 80

```python
def evaluate(row, cfg, prev_row=None, rows=None):
    f = row["degF_rolling_avg"]  # 1/5/10 min by ts_ms; use row["degF"] for raw
    if f < cfg["bounds_low_f"] or f > cfg["bounds_high_f"]:
        print(f"{row['ts']}  OOB avg  {f:.2f} F  raw={row['degF']:.2f}")
        return True
    return False
```

**Recipe 1b — Instant raw bounds (no avg)**

```python
def evaluate(row, cfg, prev_row=None, rows=None):
    f = row["degF"]
    if f < cfg["bounds_low_f"] or f > cfg["bounds_high_f"]:
        print(f"{row['ts']}  OUT OF BOUNDS  {f:.2f} F")
        return True
    return False
```

**Test:** 6 h window. If temps stay 65–68 °F you will see **0 flags** (expected).

**Demo faults:** set `bounds_low_f` = 66 in the form, or use Pi `--fault-demo`.

---

## Recipe 1b-time — UTC hour / schedule from `ts_ms`

`datetime` is always allowed (stdlib). `row["ts_ms"]` is epoch milliseconds (UTC).

```python
from datetime import datetime, timezone

def evaluate(row, cfg, prev_row=None, rows=None):
    dt = datetime.fromtimestamp(row["ts_ms"] / 1000.0, tz=timezone.utc)
    # Example: flag samples before 08:00 UTC
    if dt.hour < int(cfg.get("start_hour_utc", 8)):
        print(f"{row['ts']}  before {cfg['start_hour_utc']}:00 UTC")
        return True
    return False
```

You can also use pre-injected `datetime` / `timezone` without importing.

---

## Recipe 1c — NumPy optional (z-score spike on raw)

```python
import numpy as np

def evaluate(row, cfg, prev_row=None, rows=None):
    if rows is None or row["row"] < 10:
        return False
    vals = np.array([r["degF"] for r in rows[: row["row"] + 1]])
    z = (row["degF"] - vals.mean()) / (vals.std() + 1e-6)
    if abs(z) > float(cfg.get("z_limit", 3)):
        print(f"{row['ts']}  numpy z={z:.2f}  {row['degF']:.2f} F")
        return True
    return False
```

---

## Recipe 2 — Rolling window debounce (you code it)

**Config:** `bounds_low_f` = 65, `bounds_high_f` = 80

```python
def evaluate(row, cfg, prev_row=None, rows=None):
    f = row["degF"]
    if f < cfg["bounds_low_f"] or f > cfg["bounds_high_f"]:
        print(f"{row['ts']}  OUT OF BOUNDS  {f:.2f} F")
        return True
    return False
```

**Test:** 6 h window. If temps stay 65–68 °F you will see **0 flags** (expected).

**Demo faults:** set `bounds_low_f` = 66 in the form, or use Pi `--fault-demo`.

---

## Recipe 2 — Rolling window debounce (you code it)

Problem: one noisy sample should not trip the chart. Require **N consecutive** out-of-band samples before flagging.

**Simple pattern** — look at the last `w` rows including this one:

```python
def evaluate(row, cfg, prev_row=None, rows=None):
    w = int(cfg.get("debounce_window", 6))  # ~1 min @ 10 s MQTT
    if rows is None or row["row"] < w - 1:
        return False
    i = row["row"]
    recent = [
        rows[j]["degF"] < cfg["bounds_low_f"] or rows[j]["degF"] > cfg["bounds_high_f"]
        for j in range(i - w + 1, i + 1)
    ]
    if len(recent) == w and all(recent):
        print(f"{row['ts']}  OOB sustained ({w} samples)  {row['degF']:.2f} F")
        return True
    return False
```

**Stateful pattern** — build a running list (same idea as open-fdd rolling window):

```python
_raw = []

def evaluate(row, cfg, prev_row=None, rows=None):
    w = int(cfg.get("debounce_window", 6))
    instant = row["degF"] < cfg["bounds_low_f"] or row["degF"] > cfg["bounds_high_f"]
    _raw.append(instant)
    # Count consecutive True ending at this index
    run = 0
    for j in range(len(_raw) - 1, -1, -1):
        if _raw[j]:
            run += 1
        else:
            break
    if run >= w:
        print(f"{row['ts']}  OOB debounced  {row['degF']:.2f} F  run={run}")
        return True
    return False
```

Add **`debounce_window`** = 6 in rule config (edit JSON on Save draft) or hard-code `w = 6`.

---

## Recipe 3 — Custom avg (optional override)

`degF_rolling_avg` is already computed for you. For a **custom** window or UTC-minute buckets, mutate `rows` yourself on row 0 or use `numpy` on the `rows` list — teaching exercise only.

---

## Recipe 4 — Engine rolling avg + debounce

```python
_raw = []

def evaluate(row, cfg, prev_row=None, rows=None):
    f = row["degF_rolling_avg"]
    instant = f < cfg["bounds_low_f"] or f > cfg["bounds_high_f"]
    _raw.append(instant)
    w = int(cfg.get("debounce_window", 6))
    run = 0
    for j in range(len(_raw) - 1, -1, -1):
        if _raw[j]:
            run += 1
        else:
            break
    if run >= w:
        print(f"{row['ts']}  OOB avg+debounce  {f:.2f} F")
        return True
    return False
```

---

## Recipe 5 — Flatline: paint the whole 1-hour window (retroactive)

**Problem:** `return True` only flags the **current** row. For “stuck sensor for 1 hour,” you want the **entire hour** shaded when the fault is confirmed.

**Option A — tuple return (engine paints for you):**

```python
ONE_HOUR_MS = 60 * 60 * 1000

def get_last_1_hour(row, rows):
    now_ms = row["ts_ms"]
    start_ms = now_ms - ONE_HOUR_MS
    return [r for r in rows if start_ms <= r["ts_ms"] <= now_ms]

def evaluate(row, cfg, prev_row=None, rows=None):
    if rows is None:
        return False

    window_rows = get_last_1_hour(row, rows)
    if not window_rows:
        return False

    span_ms = window_rows[-1]["ts_ms"] - window_rows[0]["ts_ms"]
    if span_ms < ONE_HOUR_MS * 0.95:
        return False  # skip row 0 / warmup — not a full hour yet

    vals = [r["degF"] for r in window_rows]
    if max(vals) - min(vals) <= cfg["flatline_tolerance_f"]:
        print(f"FLATLINE at {row['ts']} — painting {len(window_rows)} rows")
        return True, window_rows  # <-- retroactive paint

    return False
```

**Option B — separate detect vs paint (teaching):**

```python
def apply_faults(rows, cfg):
    flags = [0] * len(rows)
    for row in rows:
        hit, window_rows = evaluate(row, cfg, rows=rows)
        if hit:
            for w in window_rows:
                flags[w["row"]] = 1
    return flags
```

Use the same `evaluate()` as Option A but return `(True, window_rows)`; define **`apply_faults`** in the same rule module. Test rule + dashboard + go-live all use the same sweep engine.

---

## Test vs Go live

| Action | Data | DB write |
|--------|------|----------|
| **Test rule** | Test window (e.g. 6 h) | No |
| **Save draft** | Rules only | `ts_ms=-2` |
| **Go live (7 d)** | Up to 168 h | FDD status `ts_ms=0` (counts + badge; chart lanes from live `/api/readings`) |

---

## YouTube demo script (suggested order)

1. Deploy stack, open Rule Lab, **Recipe 1** bounds → Test → Copy report.
2. Live-edit **Recipe 2** debounce → Test again → flags appear only after sustained OOB.
3. Live-edit **Recipe 3** 1-min avg → Test → read `avg=` vs `raw=` in print lines.
4. **Go live (7 d)** → Dashboard tab shows fault lanes on 7 d history (and avg line if Recipe 3 wrote `degF_1min_avg`).

---

## Built-in legacy rules (`fdd_rules.py`)

If custom rules are empty, scheduled FDD can use `fdd_rules.evaluate_all()` (instant flags, no debounce). Rule Lab always uses **your** Python when rules are saved in DynamoDB.
