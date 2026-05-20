# Tests (vibe_code_apps_12)

Lightweight **stdlib `unittest`** checks for pure-Python FDD logic — no AWS, no Docker.

Worth having in a tutorials repo: catches regressions when you change `fdd_rules.py` or the Rule Lab sandbox before redeploying Lambdas.

## Run locally

```bash
cd /path/to/vibe_code_apps_12
python3 -m unittest discover -s tests -v
```

## What is covered

| Module | Tests |
|--------|--------|
| `fdd_rules.py` | instant flags, bounds, flatline, rate; `rolling_window_flags` helper |
| `playground_core.py` | lint, sweep with custom `evaluate()` |
| `timeseries_enrich.py` | 1-minute rolling avg on raw timeline |

## What is not covered

- DynamoDB, IoT, SAM deploy (integration / manual CloudShell)
- Browser UI (use Rule Lab **Test rule** + `/api/health` instead)

## CI (optional)

`.github/workflows/vibe12-tests.yml` runs the same command on push when this folder changes.
