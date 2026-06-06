# FddFunction — BRICK-scoped Arrow rules via PyPI `open-fdd` 3.x

Scheduled Lambda (`rate(5 minutes)`) reads DynamoDB telemetry, runs **Arrow-only** fault rules (`apply_faults_arrow` + cookbook masks), and writes status row `ts_ms=0`.

## Stack

| Piece | Role |
|-------|------|
| `open-fdd>=3.0.1` | PyPI — `arrow_runtime.cookbook`, `run_arrow_rule` |
| `pyarrow` | Columnar historian tables (DynamoDB → `pa.Table`) |
| `brick_fdd_runner.py` | BRICK scope expansion + Arrow rule execution |
| `arrow_series.py` | Rows → Arrow table, window sizing, mask → flags |
| `rules_defaults.py` | Shipped zone temp + humidity rules (Arrow cookbook) |

Custom rules in DynamoDB (`PLATFORM_META`, `ts_ms=-2`) must define `apply_faults_arrow(table, cfg, context=None)` — legacy row `evaluate()` is not supported.

Brick FDD summaries include `open_fdd_version` and `fdd_backend: arrow`.
