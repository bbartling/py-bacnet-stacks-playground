# Expression rule cookbook (Rule Lab)

How to write **browser Python** rules for DS18B20 telemetry. The backend only:

1. Loads MQTT rows from DynamoDB (`row`, `ts_ms`, `degF`, …)
2. Calls **`evaluate(row, cfg, prev_row, rows)`** once per row
3. Stores **`True` → flag 1** on that same row index (plot + DynamoDB timeline)

**Rolling avg on every row (automatic):** before each sweep, the engine adds:

| Field | Meaning |
|-------|---------|
| `degF` | Instantaneous sample (same as MQTT) |
| `degF_raw` | Copy of instantaneous |
| `degF_rolling_avg` | Trailing mean over ~**60 s** of data at your MQTT cadence |
| `sample_period_ms` | Median gap between samples (e.g. 10000 @ 10 s) |
| `rolling_window_samples` | How many points in that avg (e.g. 6 @ 10 s) |

You still code **rolling_window debounce** yourself if you want sustained faults — see Recipe 2.

**Sandbox:** `print`, `math`, builtins, and optionally **`import numpy as np`** when Lambda has numpy (`/api/health` → `numpy_available: true`). `np` is also pre-injected if import works.

---

## Recipe 1 — Out of bounds on rolling avg (uses pre-built row field)

**Config:** `bounds_low_f` = 65, `bounds_high_f` = 80

```python
def evaluate(row, cfg, prev_row=None, rows=None):
    f = row["degF_rolling_avg"]  # auto ~60s window; use row["degF"] for raw
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
