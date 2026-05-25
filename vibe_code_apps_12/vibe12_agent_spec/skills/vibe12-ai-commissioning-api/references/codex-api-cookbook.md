# Codex API cookbook — copy/paste blocks

Replace `URL`, `TOKEN`, `SITE`, `BLD` once per session.

```bash
SITE=demo
BLD=bens-office
URL="https://YOUR.lambda-url.us-east-2.on.aws"
TOKEN="eyJ..."
AUTH=(-H "Authorization: Bearer $TOKEN")
```

## Health

```bash
curl -sS "$URL/api/health" | python3 -m json.tool
```

## Commissioning status (JSON for agent parsing)

```bash
curl -sS "$URL/api/commissioning/status/${SITE}/${BLD}?window_minutes=20" "${AUTH[@]}" \
  | python3 -m json.tool > /tmp/vibe12-commissioning.json
python3 <<'PY'
import json
d=json.load(open("/tmp/vibe12-commissioning.json"))
print("ok", d["cloud_ingest_ok"], "flow", d["series_flowing"], "/", d["series_total"])
for s in d["series"]:
    print(s["source"], s["point_id"], s["flowing"], s.get("last_value"), s.get("brick_class"))
print("actions:", *d.get("recommended_actions",[]), sep="\n ")
PY
```

## BRICK refs → external time series IDs

```bash
curl -sS "$URL/api/brick/timeseries-ref/${SITE}/${BLD}" "${AUTH[@]}" \
  | python3 -c "
import sys,json
for r in json.load(sys.stdin).get('refs',[]):
    ref=r['brick_timeseries_ref']
    print(ref['series_id'], ref['entity_id'], ref['external_ref'])
"
```

## Single series history

```bash
SERIES="demo#bens-office#office#digital-temp-degC"
curl -sS "$URL/api/series?series_ids=${SERIES}&hours=2" "${AUTH[@]}" | python3 -m json.tool
```

## Test FDD rule (no DB writes)

```bash
curl -sS -X POST "$URL/api/playground/test-rule" "${AUTH[@]}" \
  -H 'Content-Type: application/json' \
  -d '{"site_id":"demo","building_id":"bens-office","hours":2,"rule":{"id":"test-zat","title":"ZAT high","scope":{"brick_class":"Zone_Air_Temperature_Sensor"},"expression":"row[\"value\"] > 80","unit":"degF"}}' \
  | python3 -m json.tool
```

## Edge + cloud one-liner smoke

```bash
./scripts/validate_cloud_pipeline.sh
ssh ben@192.168.204.12 'journalctl -u vibe12-bacnet-read -n 2 --no-pager'
```
