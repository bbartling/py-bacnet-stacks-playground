## Day 32 – String parsing for BAS text (split, join, strip)

### Goal

Manipulate **strings** the way you do with trend filenames, CSV headers, Haystack-ish tags, or simple `name=value` lines—**split**, **join**, **strip**, case normalization. Skip “puzzle” string problems; stay close to **field data**.

### Concept

- **`strip()`** removes leading/trailing whitespace (common in CSV/API exports).
- **`split(delim)`** breaks a line into tokens.
- **`join(iterable)`** builds text efficiently from parts.
- **Case:** `lower()` / `upper()` for comparisons when vendors disagree on casing.

### How to use it

```python
line = "  Supply_Air_Temperature_Sensor, 72.4, degF  "
parts = [p.strip() for p in line.split(",")]
print(parts)  # ['Supply_Air_Temperature_Sensor', '72.4', 'degF']

def parse_float_after_colon(s):
    """Parse 'SAT: 55.2' style fragment to float."""
    left, _, right = s.partition(":")
    return float(right.strip())

print(parse_float_after_colon("MAT: 62.5"))
```

### Why this matters

Before any numeric algorithm you must **get clean numbers and identifiers**. Point lists, Brick-style labels, and historian exports are text-first. Reliable parsing prevents garbage from entering your **threshold** and **statistics** functions.

### Mini examples

- Split a BACnet-ish object string `"analogValue:12"` on `:` → `("analogValue", 12)` with `int` conversion.
- Join a list of alarm messages with `"; "` for a single log line.
- Normalize: `tag.strip().lower()` before comparing to `"occupied"`.

### Micro exercises

1. Write `parse_kv_line("  static_pressure = 1.25  ")` → `("static_pressure", 1.25)`.
2. Given multiline text with one `point,value` per line, return a `list[tuple[str, float]]` (skip blank lines).
3. Count how many lines contain the substring `"SAT"` (case insensitive).

### Key takeaway

String algorithms here are **data hygiene**: split, strip, validate—then hand floats to your HVAC math and rules.
