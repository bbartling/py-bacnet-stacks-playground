# Expression rule cookbook (Rule Lab)

How to write **browser Python** rules for DS18B20 telemetry. The backend only:

1. Loads MQTT rows from DynamoDB (`row`, `ts_ms`, `degF`, …)
2. Calls **`evaluate(row, cfg, prev_row, rows)`** once per row
3. Stores **`True` → flag 1** on that same row index (plot + DynamoDB timeline)

There is **no** automatic **rolling_window** debounce and **no** automatic **1-minute average** unless **you** add them in code (good for teaching / YouTube demos).

Optional helpers available in the sandbox (you must call them):

- `rolling_window_flags(raw_bools, window)` — debounce fault hits
- `attach_minute_rolling_avg(rows, bucket_ms=60000)` — add `degF_1min_avg` to every row
- `rolling_avg_field(row, "degF")` — read avg after attach

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

## Recipe 2 — Add rolling_window debounce (you code it)

Problem: one noisy sample should not trip the chart.

Pattern: collect raw hits in a module-level list, apply debounce **once** on the last row.

```python
_hits = []

def evaluate(row, cfg, prev_row=None, rows=None):
    hit = row["degF"] < cfg["bounds_low_f"] or row["degF"] > cfg["bounds_high_f"]
    _hits.append(hit)

    # Only on last row: convert debounced series to "did this row fault?"
    if rows is not None and row["row"] == len(rows) - 1:
        debounced = rolling_window_flags(_hits, int(cfg.get("debounce_window", 6)))
        # Re-walk is done in go-live engine per-row; for Test, flag when debounced at this index
        if debounced[-1]:
            print(f"{row['ts']}  OOB debounced")
            return True
    return hit  # instant during sweep (see note below)
```

**Simpler pattern for teaching** — debounce inside evaluate using recent history:

```python
def evaluate(row, cfg, prev_row=None, rows=None):
    if rows is None or row["row"] < 5:
        return False
    i = row["row"]
    recent = [rows[j]["degF"] < cfg["bounds_low_f"] or rows[j]["degF"] > cfg["bounds_high_f"]
              for j in range(i - 5, i + 1)]
    if sum(recent) >= 6:  # 6 consecutive True in last 6 samples
        print(f"{row['ts']}  OOB sustained")
        return True
    return False
```

**Config:** add a custom field in the form or hard-code `6` (~1 min @ 10 s MQTT).

**Recommended for go-live** — stateful debounce module:

```python
_raw = []

def evaluate(row, cfg, prev_row=None, rows=None):
    instant = row["degF"] < cfg["bounds_low_f"] or row["degF"] > cfg["bounds_high_f"]
    _raw.append(instant)
    w = int(cfg.get("debounce_window", 6))
    deb = rolling_window_flags(_raw, w)
    if deb[-1]:
        print(f"{row['ts']}  OOB (debounced)  {row['degF']:.2f} F")
        return True
    return False
```

Add config key `debounce_window` = 6 in the Rule Lab form (type manually in JSON via Save draft) or hard-code `w = 6`.

---

## Recipe 3 — 1-minute rolling average (you code it)

Enrich rows once, then evaluate on **`degF_1min_avg`** (still one flag per raw timestamp).

```python
_enriched = False

def evaluate(row, cfg, prev_row=None, rows=None):
    global _enriched
    if rows is not None and not _enriched:
        attach_minute_rolling_avg(rows, bucket_ms=int(cfg.get("avg_bucket_ms", 60000)))
        _enriched = True

    f_avg = rolling_avg_field(row, "degF")
    f_raw = row.get("degF_raw", row["degF"])

    if f_avg < cfg["bounds_low_f"] or f_avg > cfg["bounds_high_f"]:
        print(f"{row['ts']}  OOB on 1min avg  avg={f_avg:.2f}  raw={f_raw:.2f}")
        return True
    return False
```

**Config:** `bounds_low_f`, `bounds_high_f`, optionally `avg_bucket_ms` = 60000.

After **Go live**, dashboard can show purple **1-min rolling avg** line if you also save rules that call `attach_minute_rolling_avg` and the API enriches for chart — chart overlay uses `aux_series` when rows carry `degF_1min_avg`.

---

## Recipe 4 — Combine 1-min avg + rolling_window

```python
_raw = []
_enriched = False

def evaluate(row, cfg, prev_row=None, rows=None):
    global _enriched
    if rows is not None and not _enriched:
        attach_minute_rolling_avg(rows, bucket_ms=60000)
        _enriched = True

    f = rolling_avg_field(row, "degF")
    instant = f < cfg["bounds_low_f"] or f > cfg["bounds_high_f"]
    _raw.append(instant)

    w = int(cfg.get("debounce_window", 6))
    if rolling_window_flags(_raw, w)[-1]:
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
2. Live-edit **Recipe 2** debounce → Test again → more flags light up slowly.
3. Live-edit **Recipe 3** 1-min avg → Test → explain avg vs raw in print lines.
4. **Go live (7 d)** → Dashboard tab shows fault lanes on 7 d history.

---

## Built-in legacy rules (`fdd_rules.py`)

If custom rules are empty, scheduled FDD can use `fdd_rules.evaluate_all()` (also **no** backend rolling_window now). Rule Lab always uses **your** Python when rules are saved in DynamoDB.
