# Vibe12 workspace memory (curated bootstrap)

Short standing brief for agent wakes — not a transcript. Detail: `memory/YYYY-MM-DD.md`.

## Stack (Phase 0 — Ben's office)

| Layer | Fact |
|-------|------|
| Edge Pi | `192.168.204.12` · user `ben` |
| Site / building | `demo` / `bens-office` |
| Read driver | `vibe12-bacnet-read.service` · **60 s** interval · 6 MQTT samples/cycle |
| BACnet | MS/TP via `2000:7@192.168.204.200` · device **5007** · bind `192.168.204.12/24:47809` |
| GPIO | DS18B20 → `office/digital-temp-degC|degF` · BRICK `Zone_Air_Temperature_Sensor` |
| MQTT client | `basicPubSub` · topic prefix `vibe12` |
| Cloud | `vibe12cloud` · `us-east-2` · rule `vibe12_telemetry_ingest` |
| Dashboard | Lambda URL in `aws_cloud_pipeline/DEPLOYED.md` · login `engineer` |
| IoT policy | Must allow `topic/vibe12/+/+/+/+/telemetry` **and** `topic/vibe12/demo/bens-office/*` |

## Standing decisions

- **One MQTT client** on Pi: read driver publishes BACnet + GPIO; `bacnet-ds18b20` **without** `--aws-iot`.
- **Ingest** writes `brick_timeseries_ref` + `external_ref` (= DynamoDB `device_id`) on every sample.
- **Agents** use HTTP commissioning APIs before FDD go-live; human validates BRICK via SparkQL.
- **Deploy cloud** from bensserver: `scripts/deploy_cloud_from_bensserver.sh` (not CloudShell-only).
- **Lambda runtime** `python3.12` for local SAM build on bensserver.

## Smoke (expected healthy)

- `GET /api/commissioning/status/demo/bens-office` → `cloud_ingest_ok: true`, `series_flowing: 6`
- Pi journal: `published 6 samples` ~every 60 s
- `./scripts/fetch_bacnet_pcap.sh` → `~/captures/bacnet.pcap`

## Open loops

- Dashboard `/api/readings` plots one primary ZAT series; multi-series UI uses `/api/series` or commissioning status.
- Rotate IAM access keys after lab testing (keys have appeared in terminal history).
- Optional: Codex cron re-enable when `BUILD_CHECKPOINTS.md` queue is ready.

## Doc entry points

- Agent spec: `vibe12_agent_spec/AGENTS.md`
- APIs: `docs/ai-commissioning-api.md` · skill `skills/vibe12-ai-commissioning-api/`
- Phase 0: `docs/phase-0-bens-office-lab.md`
