
=== MEMORY: MEMORY.md ===
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

=== GUARDRAILS: GUARDRAILS.md ===
# Vibe12 agent guardrails

## Never

- Commit `samconfig.toml`, IoT `*.private.key`, or `aws_iot_certs/` PEMs
- Paste production passwords or access keys into `memory/*.md` or skills
- Run BACnet **writes** to field devices without human sign-off and `safe-bacnet-writes` review
- Change IoT policy in AWS without documenting in `memory/integrations/aws-iot.md`
- Assume `cloud_ingest_ok` from Pi journal alone — always call commissioning API or DynamoDB

## Always

- Read `memory/commissioning/PHASE_NOTEPAD.md` before changing bind address or `points.csv`
- Use **absolute** scp paths for Pi (`/home/ben/vibe_code_apps_12/...`)
- Bump `DeployRevision` in `samconfig.toml` on each cloud deploy
- Run `validate_cloud_pipeline.sh` after cloud or API changes
- Keep human in the loop for SSH and point enablement

## Scope discipline

- One BUILD_CHECKPOINTS slice per wake when using automation
- Prefer smallest diff; match existing Ansible and Lambda patterns

=== daily: memory/2026-05-25.md ===
# 2026-05-25 — agent daily log

## Summary

- End-to-end telemetry: Pi 60 s scrape → IoT → ingest → DynamoDB → commissioning API (6/6 flowing).
- BRICK `brick_timeseries_ref` auto-written on ingest.
- Agent spec scaffold: `vibe12_agent_spec/` (AGENTS, MEMORY, skills, CLI).

## Verification

- `./scripts/validate_cloud_pipeline.sh` OK
- `~/captures/bacnet.pcap` pulled via `fetch_bacnet_pcap.sh`
- GH Actions `9079590`+ green after import fix

## Risks

- IAM lab keys in history — rotate before production
- Dashboard single-series `/api/readings` — use commissioning API for multi-source

=== PHASE_NOTEPAD: memory/commissioning/PHASE_NOTEPAD.md ===
# Phase notepad — demo / bens-office (agent contract)

Human fills § A–D; agent reads **before** changing bind, `points.csv`, or IoT policy.

## § A — BACnet bind (head-end on Pi)

| Field | Value |
|-------|--------|
| Pi IP | `192.168.204.12` |
| Edge bind | `192.168.204.12/24:47809` (Vibe12Edge) |
| PiTemp local | UDP `47808` |
| MS/TP router | `192.168.204.200` · net `2000` |
| Target device | instance **5007** |

## § B — Building scope

| Field | Value |
|-------|--------|
| site_id | `demo` |
| building_id | `bens-office` |

## § C — Staged devices / points

Source: `commissioning/demo/bens-office/points.csv` (4 BACnet points enabled).

| point_id | BRICK class | Notes |
|----------|-------------|--------|
| `5007-analog-input-10014` | Zone_Air_Temperature_Sensor | STAT ZN-T (MSTP) |
| `5007-analog-input-1192` | Discharge_Air_Temperature_Sensor | DUCT-T |
| `5007-analog-input-1168` | Outside_Air_Humidity_Sensor | OA-H |
| `5007-analog-input-1173` | Outside_Air_Temperature_Sensor | OA-T |
| `digital-temp-degC` / `digital-temp-degF` | Zone_Air_Temperature_Sensor | GPIO DS18B20 · system `office` |

## § D — Dial-in URLs

| Surface | URL |
|---------|-----|
| Cloud dashboard | See `aws_cloud_pipeline/DEPLOYED.md` → DashboardUrl |
| Pi SSH | `ben@192.168.204.12` |

## § E — Phase strip

| Phase | Status | Next |
|-------|--------|------|
| Edge deploy | done | Re-run Ansible after CSV changes |
| MQTT → IoT | done | Policy `vibe12/+/+/+/+/telemetry` |
| Cloud ingest | done | `cloud_ingest_ok` via API |
| BRICK model | in progress | Human + SparkQL validation |
| FDD go-live | pending | Rule Lab after BRICK sign-off |

=== BUILD_CHECKPOINTS: BUILD_CHECKPOINTS.md ===
# Vibe12 build checkpoints (agent queue)

Pick **one** slice per automated wake. Mark done in "Done recently" with UTC timestamp.

## Human sign-off (required before new sites)

- [ ] I authorize BACnet RPM reads for devices listed in `commissioning/.../points.csv` on this job.
- [ ] IoT device policy allows hierarchical `vibe12/.../telemetry` publish for this cert.
- [ ] Cloud `WebPassword` / `AuthSecret` are set in local `samconfig.toml` (not committed).

Signed off for **demo / bens-office**: lab bench 2026-05-25 (Pi scrape + cloud ingest verified).

## Current sprint

| Priority | Slice | Skill |
|----------|-------|-------|
| P0 | Keep telemetry flowing (6/6 series) | `vibe12-ai-commissioning-api` |
| P1 | BRICK graph + canonical model for demo building | `vibe12-brick-data-model` |
| P2 | FDD rule test + go-live for one ZAT rule | `vibe12-fdd-rule-lab` |
| P3 | Multi-series dashboard chart (MSTP + GPIO) | `apps/vibe12-web` |

## Done recently

- 2026-05-25 — Phase 0: IoT policy fixed; ingest BRICK refs; commissioning APIs; Pi 60 s → AWS; pcap easy button; agent spec scaffold.

## Next for agent (ordered)

1. Run `./scripts/validate_cloud_pipeline.sh` and `ssh` Pi journal — confirm still 6/6 flowing.
2. `GET /api/brick/timeseries-ref/demo/bens-office` — ensure graph bootstrap matches registry.
3. Human: confirm ZAT points match job (MSTP STAT-ZN-T + GPIO BenOffice-ZAT).
4. Draft one FDD rule in Rule Lab; `POST /api/playground/test-rule` then go-live when human approves.
5. Append wake notes to `memory/YYYY-MM-DD.md`; promote deltas to `MEMORY.md`.

## Verification commands

```bash
cd ~/py-bacnet-stacks-playground/vibe_code_apps_12
./scripts/validate_cloud_pipeline.sh
python3 -m unittest discover -s tests -q
cd apps/vibe12-web && npm test
```

=== skill index ===
skills/vibe12-agent-runner/SKILL.md
skills/vibe12-ai-commissioning-api/SKILL.md
skills/vibe12-ansible-edge/SKILL.md
skills/vibe12-brick-data-model/SKILL.md
skills/vibe12-cloud-deploy/SKILL.md
skills/vibe12-fdd-rule-lab/SKILL.md
skills/vibe12-wire-pcap/SKILL.md
