# Expression rule cookbook (Rule Lab)

Copy a recipe into **Rule Lab → Python editor**, set **Parameters (cfg)** from the table, click **Test rule** (6 h preview), then **Save draft** or **Write to database**.

## How rules run

| Topic | Detail |
|-------|--------|
| Entry point | `evaluate(row, cfg, prev_row=None, rows=None)` — required |
| Row fields | `row`, `ts_ms`, `ts`, `temp`, `temp_raw`, `temp_rolling_avg`, `degF`, `degC`, `degF_rolling_avg`, `sample_period_ms`, `rolling_avg_minutes`, `samples_in_avg` |
| Config | Use `cfg_threshold(cfg, "key")` — values follow **Rule unit** (°F or °C). Add keys via **+ Parameter** or **Add preset…** |
| Helpers | `temp_unit_symbol(cfg)`, `math`, `datetime`, optional `numpy as np` |
| Instant flag | `return True` — flags **this row only** |
| Retroactive lane | `return True, window_rows` — paints every row in `window_rows` on the chart (recommended for lookback rules) |
| Batch mode | Optional `apply_faults(rows, cfg) -> list[bool]` — see Recipe 10 |

**Tip:** At ~10 s MQTT, 6 samples ≈ 1 minute, 360 samples ≈ 1 hour. Use `FILL_RATIO = 0.95` so the window is nearly full before evaluating.

---

## Zone starting points (DS18B20 @ ~10 s)

| Recipe | Config key(s) | Start values (°F / °C) |
|--------|---------------|-------------------------|
| 1 — Flatline 1 h | `flatline_tolerance` | **0.10** / **0.03** |
| 2 — Rate 1 h | `max_temp_per_hour` | **5.0** / **3.0** |
| 3 — Rate 15 m | `max_temp_per_15min` | **2.0** / **1.1** |
| 4 — Spread 1 h | `max_spread` | **4.0** / **2.2** |
| 5 — Spread 15 m | `max_spread_15min` | **2.5** / **1.4** |
| 6 — Out of bounds | `bounds_low`, `bounds_high` | **65**, **80** / **18**, **27** |
| 7 — Flatline N samples | `flatline_tolerance`, `flatline_window` | **0.05** / **0.03**, **18** |
| 8 — OOB debounced | `bounds_low`, `bounds_high`, `rolling_window` | **65**, **80**, **6** |
| 9 — Rate instant (pair) | `max_temp_per_minute` | **2.0** / **1.1** |

---

## Recipe 1 — Flatline (1 hour window)

Sensor stuck: max − min over the last hour is below tolerance. Paints the full hour when detected.

**Config:** `flatline_tolerance` = **0.10** (°F) or **0.03** (°C)

**Test tip:** Use **Test window ≥ 2 h** (default). `print()` runs only when a fault fires; enable **Verbose prints (window trace)** to see sample 1 h spreads without changing code.

```python
ONE_HOUR_MS = 60 * 60 * 1000
FILL_RATIO = 0.95


def get_last_1_hour(row, rows):
    now_ms = row["ts_ms"]
    start_ms = now_ms - ONE_HOUR_MS
    return [r for r in rows if start_ms <= r["ts_ms"] <= now_ms]


def evaluate(row, cfg, prev_row=None, rows=None):
    if rows is None:
        return False

    window_rows = get_last_1_hour(row, rows)
    if len(window_rows) < 2:
        return False

    span_ms = window_rows[-1]["ts_ms"] - window_rows[0]["ts_ms"]
    if span_ms < ONE_HOUR_MS * FILL_RATIO:
        return False

    sym = temp_unit_symbol(cfg)
    vals = [r["temp"] for r in window_rows]
    spread = max(vals) - min(vals)
    tol = cfg_threshold(cfg, "flatline_tolerance")

    if spread < tol:
        print(
            f"row={row['row']} ts={row['ts']} "
            f"FLATLINE 1h spread={spread:.3f} {sym} < tol={tol:.3f}"
        )
        return True, window_rows

    return False
```

---

## Recipe 2 — Rate of change (1 hour, net °F/hr)

Net temperature change over a full hour, divided by elapsed hours.

**Config:** `max_temp_per_hour` = **5.0** (°F/hr) or **3.0** (°C/hr)

```python
ONE_HOUR_MS = 60 * 60 * 1000
FILL_RATIO = 0.95


def get_last_1_hour(row, rows):
    now_ms = row["ts_ms"]
    start_ms = now_ms - ONE_HOUR_MS
    return [r for r in rows if start_ms <= r["ts_ms"] <= now_ms]


def evaluate(row, cfg, prev_row=None, rows=None):
    if rows is None:
        return False

    window_rows = get_last_1_hour(row, rows)
    if len(window_rows) < 2:
        return False

    span_ms = window_rows[-1]["ts_ms"] - window_rows[0]["ts_ms"]
    if span_ms < ONE_HOUR_MS * FILL_RATIO:
        return False

    dt_hr = (window_rows[-1]["ts_ms"] - window_rows[0]["ts_ms"]) / 3600000.0
    if dt_hr <= 0:
        return False

    sym = temp_unit_symbol(cfg)
    v0 = window_rows[0]["temp"]
    v1 = window_rows[-1]["temp"]
    rate_hr = abs(v1 - v0) / dt_hr
    lim = cfg_threshold(cfg, "max_temp_per_hour")

    print(
        f"row={row['row']} ts={row['ts']} "
        f"rate={rate_hr:.2f} {sym}/hr ({v0:.2f} -> {v1:.2f})"
    )

    if rate_hr > lim:
        print(f"RATE/Hr: painting {len(window_rows)} rows")
        return True, window_rows

    return False
```

---

## Recipe 3 — Rate of change (15 minutes)

Same as Recipe 2, but normalized to a 15-minute equivalent rate.

**Config:** `max_temp_per_15min` = **2.0** (°F) or **1.1** (°C)

```python
FIFTEEN_MIN_MS = 15 * 60 * 1000
FILL_RATIO = 0.95


def get_last_15_min(row, rows):
    now_ms = row["ts_ms"]
    start_ms = now_ms - FIFTEEN_MIN_MS
    return [r for r in rows if start_ms <= r["ts_ms"] <= now_ms]


def evaluate(row, cfg, prev_row=None, rows=None):
    if rows is None:
        return False

    window_rows = get_last_15_min(row, rows)
    if len(window_rows) < 2:
        return False

    span_ms = window_rows[-1]["ts_ms"] - window_rows[0]["ts_ms"]
    if span_ms < FIFTEEN_MIN_MS * FILL_RATIO:
        return False

    dt_min = (window_rows[-1]["ts_ms"] - window_rows[0]["ts_ms"]) / 60000.0
    if dt_min <= 0:
        return False

    sym = temp_unit_symbol(cfg)
    delta = abs(window_rows[-1]["temp"] - window_rows[0]["temp"])
    rate_15 = delta * (15.0 / dt_min)
    lim = cfg_threshold(cfg, "max_temp_per_15min")

    print(
        f"row={row['row']} ts={row['ts']} "
        f"equiv {rate_15:.2f} {sym} per 15 min"
    )

    if rate_15 > lim:
        print(f"RATE/15m: painting {len(window_rows)} rows")
        return True, window_rows

    return False
```

---

## Recipe 4 — Spread / MIN–MAX (1 hour)

Zone swung too much: peak − valley over one hour exceeds limit (short cycling, stuck damper, etc.).

**Config:** `max_spread` = **4.0** (°F) or **2.2** (°C)

```python
ONE_HOUR_MS = 60 * 60 * 1000
FILL_RATIO = 0.95


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
    if span_ms < ONE_HOUR_MS * FILL_RATIO:
        return False

    sym = temp_unit_symbol(cfg)
    vals = [r["temp"] for r in window_rows]
    lo, hi = min(vals), max(vals)
    spread = hi - lo
    lim = cfg_threshold(cfg, "max_spread")

    print(
        f"row={row['row']} ts={row['ts']} "
        f"spread={spread:.2f} {sym} (min={lo:.2f} max={hi:.2f})"
    )

    if spread > lim:
        print(f"SPREAD/1h: painting {len(window_rows)} rows")
        return True, window_rows

    return False
```

---

## Recipe 5 — Spread / MIN–MAX (15 minutes)

Short-window spread — catches fast hunting or sudden step changes.

**Config:** `max_spread_15min` = **2.5** (°F) or **1.4** (°C)

```python
FIFTEEN_MIN_MS = 15 * 60 * 1000
FILL_RATIO = 0.95


def get_last_15_min(row, rows):
    now_ms = row["ts_ms"]
    start_ms = now_ms - FIFTEEN_MIN_MS
    return [r for r in rows if start_ms <= r["ts_ms"] <= now_ms]


def evaluate(row, cfg, prev_row=None, rows=None):
    if rows is None:
        return False

    window_rows = get_last_15_min(row, rows)
    if not window_rows:
        return False

    span_ms = window_rows[-1]["ts_ms"] - window_rows[0]["ts_ms"]
    if span_ms < FIFTEEN_MIN_MS * FILL_RATIO:
        return False

    sym = temp_unit_symbol(cfg)
    vals = [r["temp"] for r in window_rows]
    lo, hi = min(vals), max(vals)
    spread = hi - lo
    lim = cfg_threshold(cfg, "max_spread_15min")

    print(
        f"row={row['row']} ts={row['ts']} "
        f"spread={spread:.2f} {sym} (min={lo:.2f} max={hi:.2f})"
    )

    if spread > lim:
        print(f"SPREAD/15m: painting {len(window_rows)} rows")
        return True, window_rows

    return False
```

---

## Recipe 6 — Out of bounds (instant, rolling avg)

Flags the current row when smoothed temperature is outside the band. Matches the default **Out of bounds** rule.

**Config:** `bounds_low` = **65**, `bounds_high` = **80** (°F) — or **18** / **27** (°C)

Set **Rolling avg** in the toolbar to **1 min** (or **10 min** for slower response).

```python
def evaluate(row, cfg, prev_row=None, rows=None):
    sym = temp_unit_symbol(cfg)
    low = cfg_threshold(cfg, "bounds_low")
    high = cfg_threshold(cfg, "bounds_high")

    # Prefer rolling avg when present (Rule Lab computes from toolbar setting)
    if "temp_rolling_avg" in row:
        v = row["temp_rolling_avg"]
        kind = "avg"
    elif "degF_rolling_avg" in row:
        v = row["degF_rolling_avg"]
        kind = "degF_avg"
    else:
        v = row["temp"]
        kind = "raw"

    if v < low or v > high:
        print(
            f"{row['ts']}  OOB {kind}  {v:.2f} {sym}  "
            f"(band {low:.1f}–{high:.1f}, raw={row['temp']:.2f})"
        )
        return True

    return False
```

---

## Recipe 7 — Flatline (N consecutive samples)

Sample-count window (not wall-clock). Good when MQTT spacing is steady (~10 s → 18 samples ≈ 3 min).

**Config:** `flatline_tolerance` = **0.05**, `flatline_window` = **18**

```python
def evaluate(row, cfg, prev_row=None, rows=None):
    if rows is None:
        return False

    sym = temp_unit_symbol(cfg)
    w = int(cfg.get("flatline_window", 18))
    if w < 2:
        w = 2
    if row["row"] < w - 1:
        return False

    i = row["row"]
    win = rows[i - w + 1 : i + 1]
    vals = [r["temp"] for r in win]
    tol = cfg_threshold(cfg, "flatline_tolerance")
    spread = max(vals) - min(vals)

    if spread < tol:
        print(
            f"{row['ts']}  FLATLINE  w={w}  spread={spread:.3f} {sym}  "
            f"tol={tol:.3f}"
        )
        return True, win

    return False
```

---

## Recipe 8 — Out of bounds (debounced / sustained)

Requires **every** sample in the last N rows to be out of band before flagging (~1 min at 6 × 10 s). Reduces flicker from noise.

**Config:** `bounds_low` = **65**, `bounds_high` = **80**, `rolling_window` = **6**  
Add `rolling_window` with **+ Parameter** (integer, default 6).

```python
def _oob(r, low, high):
    v = r.get("temp_rolling_avg", r["temp"])
    return v < low or v > high


def evaluate(row, cfg, prev_row=None, rows=None):
    if rows is None:
        return False

    sym = temp_unit_symbol(cfg)
    low = cfg_threshold(cfg, "bounds_low")
    high = cfg_threshold(cfg, "bounds_high")
    n = int(cfg.get("rolling_window", 6))
    if n < 1:
        n = 1

    if row["row"] < n - 1:
        return False

    i = row["row"]
    win = rows[i - n + 1 : i + 1]

    if all(_oob(r, low, high) for r in win):
        v = win[-1].get("temp_rolling_avg", win[-1]["temp"])
        print(
            f"{row['ts']}  OOB sustained {n} samples  "
            f"last={v:.2f} {sym}  band {low:.1f}–{high:.1f}"
        )
        return True, win

    return False
```

---

## Recipe 9 — Rate instant (previous sample pair)

Fast spike detector: rate between this row and the previous sample only. Default **Rate > limit (per minute)** style.

**Config:** `max_temp_per_minute` = **2.0** (°F/min) or **1.1** (°C/min)

```python
def evaluate(row, cfg, prev_row=None, rows=None):
    if not prev_row:
        return False

    sym = temp_unit_symbol(cfg)
    dt_ms = row["ts_ms"] - prev_row["ts_ms"]
    if dt_ms <= 0:
        return False

    dt_min = dt_ms / 60000.0
    rate = abs(row["temp"] - prev_row["temp"]) / dt_min
    lim = cfg_threshold(cfg, "max_temp_per_minute")

    if rate > lim:
        print(
            f"{row['ts']}  RATE/min  {rate:.2f} {sym}/min  "
            f"({prev_row['temp']:.2f} -> {row['temp']:.2f})"
        )
        return True

    return False
```

---

## Recipe 10 — Verbose trace (debug / LLM report)

Prints every row when **Verbose prints** is checked in Rule Lab. Use to learn row fields or paste console into an LLM.

**Config:** none required

```python
def evaluate(row, cfg, prev_row=None, rows=None):
    sym = temp_unit_symbol(cfg)
    avg = row.get("temp_rolling_avg", row["temp"])
    print(
        f"#{row['row']:4d} {row['ts']}  "
        f"raw={row['temp']:.2f} avg={avg:.2f} {sym}  "
        f"samples_in_avg={row.get('samples_in_avg', '?')}"
    )
    return False
```

---

## Recipe 11 — Batch sweep with `apply_faults` (advanced)

Runs `evaluate` once per row but merges painted windows in a second pass. Useful for heavy rules or custom merge logic.

**Config:** same as Recipe 2 (`max_temp_per_hour` = **5.0**)

```python
ONE_HOUR_MS = 60 * 60 * 1000
FILL_RATIO = 0.95


def get_last_1_hour(row, rows):
    now_ms = row["ts_ms"]
    start_ms = now_ms - ONE_HOUR_MS
    return [r for r in rows if start_ms <= r["ts_ms"] <= now_ms]


def evaluate(row, cfg, prev_row=None, rows=None):
    if rows is None:
        return False

    window_rows = get_last_1_hour(row, rows)
    if len(window_rows) < 2:
        return False

    span_ms = window_rows[-1]["ts_ms"] - window_rows[0]["ts_ms"]
    if span_ms < ONE_HOUR_MS * FILL_RATIO:
        return False

    dt_hr = span_ms / 3600000.0
    if dt_hr <= 0:
        return False

    v0 = window_rows[0]["temp"]
    v1 = window_rows[-1]["temp"]
    rate_hr = abs(v1 - v0) / dt_hr
    lim = cfg_threshold(cfg, "max_temp_per_hour")

    if rate_hr > lim:
        return True, window_rows
    return False


def apply_faults(rows, cfg):
    flags = [0] * len(rows)
    for row in rows:
        hit, window_rows = evaluate(row, cfg, rows=rows)
        if hit:
            for w in window_rows:
                flags[w["row"]] = 1
    return flags
```

---

## Recipe 12 — SAT–RAT spread (multi-sensor / Brick)

Cross-sensor mechanical rule using `series` context. Map aliases in rule **config**:

```json
{
  "max_spread": 25.0,
  "series_aliases": {
    "SAT": "acme#tower-a#ahu-1#3456788-analog-input-2",
    "RAT": "acme#tower-a#ahu-1#3456788-analog-input-4"
  }
}
```

Or use Brick tags if series IDs match alias keys after graph import.

```python
def evaluate(row, cfg, prev_row=None, rows=None, series=None):
    if not series:
        return False
    sat = series.get("SAT", {}).get("current")
    rat = series.get("RAT", {}).get("current")
    if sat is None or rat is None:
        return False
    spread = abs(float(sat) - float(rat))
    if spread > cfg["max_spread"]:
        print(f"{row['ts']}  SAT-RAT spread={spread:.1f}  SAT={sat} RAT={rat}")
        return True
    return False
```

## Recipe 13 — All SAT sensors flatline (by Brick class)

Use **Test rule** with building scope after multi-series data is loaded, or query `/api/series/by-tag?brick_class=Supply_Air_Temperature_Sensor`.

```python
def evaluate(row, cfg, prev_row=None, rows=None, series=None):
  # Primary row is first series in scope; use series["SAT"]["values"] for window
  if not series or "SAT" not in series:
      return False
  vals = [v for v in series["SAT"]["values"] if v is not None][-18:]
  if len(vals) < 18:
      return False
  tol = cfg.get("flatline_tolerance", 0.05)
  if max(vals) - min(vals) < tol:
      print(f"{row['ts']}  SAT flatline spread={max(vals)-min(vals):.3f}")
      return True
  return False
```

---

## Quick workflow

1. **+ Add rule** or pick an existing rule in the dropdown.
2. Paste recipe code; add cfg keys from the table (**Add preset…**).
3. Set **Rule unit** to match your thresholds (°F vs °C).
4. **Test rule** — console shows `print` output; chart preview uses test window only.
5. **Copy report for LLM** — full rule + sweep log for debugging.
6. **Save draft** — rules only in DynamoDB (`ts_ms=-2`).
7. **Write to database** — rules + 7 d FDD backfill + status row.

## Related

- Default shipped rules: `web_lambda/rules_defaults.py`
- Retroactive painting tests: `tests/test_retroactive_faults.py`
- Synthetic faults on Pi: `fault_demo_schedule.py` + `temp_sensor_server --fault-demo`
