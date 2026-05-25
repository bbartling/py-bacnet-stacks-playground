# Tests (vibe_code_apps_12)

Lightweight **stdlib `unittest`** checks for pure-Python FDD logic — no AWS, no Docker.

## Run locally

```bash
cd /path/to/vibe_code_apps_12
python3 -m unittest discover -s tests -v
```

From repo root:

```bash
cd py-bacnet-stacks-playground/vibe_code_apps_12
python3 -m unittest discover -s tests -v
```

## What is covered

| File | Tests |
|------|--------|
| `test_fdd_rules.py` | Instant flags, bounds, flatline, rate |
| `test_playground_core.py` | Lint, sweep, row enrich, blocked imports |
| `test_row_enrich.py` | Time-based `degF_rolling_avg` (1/5/10 min), numpy sandbox |
| `test_rolling_avg.py` | `normalize_rolling_avg_minutes`, `prepare_rows_for_evaluate` |
| `test_afdd_logging.py` | `AfddLog`, `debug_payload`, chunked per-chunk error recovery |
| `test_afdd_chunked.py` | Chunked AFDD merge across time windows |
| `test_go_live_constants.py` | Go live hard-coded 6 h batches, 168 h max |
| `test_retroactive_faults.py` | `(True, window_rows)` and `apply_faults()` |
| `test_units.py` | Imperial default, metric rule unit, cfg_threshold |
| `test_rules_defaults.py` | `rules_meta`, `chart_guides`, defaults; **independent `brick_scope` per rule** |
| `test_slim_fdd_summary.py` | Go-live DynamoDB payload slimming |
| `test_web_auth.py` | Single-user login tokens (`web_auth.py`) |
| `test_brick_scope_options.py` | Registry/model BRICK class picklists |
| `test_mqtt_topic_parse.py` | MQTT topic + BACnet row parsing (ingest) |
| `test_edge_mqtt_payload.py` | Edge publish payload shape |

**NumPy:** `test_numpy_import_in_rule` runs when numpy is installed locally (same as Lambda after `sam build`).

## Frontend (`apps/vibe12-web`)

```bash
cd apps/vibe12-web
npm ci
npm test          # vitest: logger + api-client
npm run build
```

## What is not covered

- DynamoDB, IoT, SAM deploy (integration / manual CloudShell)
- Full browser E2E (manual: login, chart, Rule Lab test)

## CI

Root `.github/workflows/vibe12-tests.yml`: Python unittest matrix + **vibe12-web** `npm test` / `npm run build`.
