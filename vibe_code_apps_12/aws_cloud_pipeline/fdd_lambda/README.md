# open-fdd on AWS (scheduled Lambda)

Uses your **[open-fdd](https://github.com/bbartling/open-fdd)** engine (`pip install "open-fdd[engine]"`) on DynamoDB telemetry every **5 minutes**.

## Rules (`rules/*.yaml`)

| File | Type | What it checks |
|------|------|----------------|
| `ds18b20_temp_bounds.yaml` | **bounds** | **65–80 °F** ([cookbook — sensor bounds](https://github.com/bbartling/open-fdd/blob/master/docs/expression_rule_cookbook.md#sensor-validation-bounds--flatline)) |
| `ds18b20_temp_flatline.yaml` | **flatline** | Stuck sensor (~3 min window at 10 s samples) |
| `ds18b20_temp_rate_per_hour.yaml` | **expression** | Change faster than **15 °F/hour** |
| `ds18b20_temp_rate_per_minute.yaml` | **expression** | Change faster than **2 °F/minute** |

Tune thresholds in YAML, redeploy the stack.

## Deploy

Included in `template.yaml` as **container** Lambda (`Dockerfile` — pandas + open-fdd).

CloudShell (Docker required for `sam build`):

```bash
cd aws_cloud_pipeline
rm -rf .aws-sam
sam build --no-cached
sam deploy --force-upload
```

First FDD run may show **PENDING** on the dashboard until the schedule fires (≤5 min).

## Output

Writes DynamoDB item `device_id` + `ts_ms = 0` with `fdd_status`, `active_flags`, `summary_json`. The **web** dashboard reads this as `fdd_open` in `/api/readings`.
