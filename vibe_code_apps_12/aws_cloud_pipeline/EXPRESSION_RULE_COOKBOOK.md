# Expression rule cookbook (Rule Lab)

How to write **browser Python** rules for DS18B20 telemetry. The backend only:

1. Loads MQTT rows from DynamoDB (`row`, `ts_ms`, `degF`, …)
2. Calls **`evaluate(row, cfg, prev_row, rows)`** once per row
3. Stores **`True` → flag 1** on that same row index (plot + DynamoDB timeline)

There are **no** backend helpers for **rolling_window** debounce or **1-minute average**. You write that logic yourself in the Rule Lab editor so you can see exactly how it works (great for teaching / YouTube).

**Sandbox:** `print`, `math`, builtins (`len`, `sum`, `range`, …) only — no `import` except `math`.

---

## Recipe 1 — Out of bounds (instant, no extras)

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

## Recipe 3 — 1-minute rolling average (you code it)

Bucket samples by UTC minute (`ts_ms // 60000`), compute mean per bucket, then evaluate on the average while flags still align to **raw** timestamps.

Run enrichment **once** on the first row; mutate `rows` in place so the dashboard can plot `degF_1min_avg` if you **Go live**:

```python
_buckets_done = False

def _attach_1min_avg(rows, bucket_ms=60000):
    """Pure Python — no backend helper."""
    buckets = {}
    for i, r in enumerate(rows):
        r["degF_raw"] = float(r["degF"])
        r["degC_raw"] = float(r.get("degC", 0))
        b = (int(r["ts_ms"]) // bucket_ms) * bucket_ms
        buckets.setdefault(b, []).append(i)
    for indices in buckets.values():
        f_vals = [rows[i]["degF_raw"] for i in indices]
        avg_f = sum(f_vals) / len(f_vals)
        for i in indices:
            rows[i]["degF_1min_avg"] = avg_f

def evaluate(row, cfg, prev_row=None, rows=None):
    global _buckets_done
    if rows is not None and not _buckets_done:
        _attach_1min_avg(rows, int(cfg.get("avg_bucket_ms", 60000)))
        _buckets_done = True

    f_avg = row.get("degF_1min_avg", row["degF"])
    f_raw = row.get("degF_raw", row["degF"])

    if f_avg < cfg["bounds_low_f"] or f_avg > cfg["bounds_high_f"]:
        print(f"{row['ts']}  OOB on 1min avg  avg={f_avg:.2f}  raw={f_raw:.2f}")
        return True
    return False
```

**Config:** `bounds_low_f`, `bounds_high_f`, optional `avg_bucket_ms` = 60000.

After **Go live**, if your rule sets `degF_1min_avg` on `rows`, the Dashboard may show a purple **1-min rolling avg** line (`aux_series` reads keys your code wrote — not computed by the server).

---

## Recipe 4 — 1-min avg + rolling window (both in browser)

```python
_buckets_done = False
_raw = []

def _attach_1min_avg(rows, bucket_ms=60000):
    buckets = {}
    for i, r in enumerate(rows):
        r["degF_raw"] = float(r["degF"])
        b = (int(r["ts_ms"]) // bucket_ms) * bucket_ms
        buckets.setdefault(b, []).append(i)
    for indices in buckets.values():
        avg_f = sum(rows[i]["degF_raw"] for i in indices) / len(indices)
        for i in indices:
            rows[i]["degF_1min_avg"] = avg_f

def evaluate(row, cfg, prev_row=None, rows=None):
    global _buckets_done
    if rows is not None and not _buckets_done:
        _attach_1min_avg(rows)
        _buckets_done = True

    f = row.get("degF_1min_avg", row["degF"])
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
| **Go live (7 d)** | Up to 168 h | FDD status `ts_ms=0` + `flag_series` |

---

## YouTube demo script (suggested order)

1. Deploy stack, open Rule Lab, **Recipe 1** bounds → Test → Copy report.
2. Live-edit **Recipe 2** debounce → Test again → flags appear only after sustained OOB.
3. Live-edit **Recipe 3** 1-min avg → Test → read `avg=` vs `raw=` in print lines.
4. **Go live (7 d)** → Dashboard tab shows fault lanes on 7 d history (and avg line if Recipe 3 wrote `degF_1min_avg`).

---

## Built-in legacy rules (`fdd_rules.py`)

If custom rules are empty, scheduled FDD can use `fdd_rules.evaluate_all()` (instant flags, no debounce). Rule Lab always uses **your** Python when rules are saved in DynamoDB.
