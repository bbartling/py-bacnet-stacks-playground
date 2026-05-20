# FddFunction — pure Python (no Docker / open-fdd)

Scheduled Lambda (`rate(5 minutes)`) reads DynamoDB telemetry, runs fault rules in `fdd_rules.py`, writes status row `ts_ms=0`.

## Rules (same as former YAML)

| Flag | Logic |
|------|--------|
| `temp_out_of_bounds_flag` | °F outside 65–80 |
| `temp_flatline_flag` | spread &lt; 0.05 °F over 18 samples |
| `temp_rate_per_hour_flag` | &gt; 15 °F/hour |
| `temp_rate_per_minute_flag` | &gt; 2 °F/minute |

Flags are **instant** per sample. Debounce and 1-min avg are **browser-only** — see [EXPRESSION_RULE_COOKBOOK.md](../EXPRESSION_RULE_COOKBOOK.md).

Legacy `rules/*.yaml` kept for reference only; engine is `fdd_rules.py`.
