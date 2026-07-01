# Vibe Code App 18 — DIY BAS / Haystack data lake (Rust)

**Active featured build.** Spec-driven, **read-only** Rust control plane for collecting Niagara / JACE / nHaystack telemetry into Postgres, serving sanitized current values to **Open-FDD**, and operating sites over a private VPN/Tailscale network.

| Item | Link |
| --- | --- |
| **Agent prompt (full spec)** | [AGENTS.md](./AGENTS.md) |
| **GitHub Discussion** | [#5 — Agent prompt to build a DIY data lake](https://github.com/bbartling/py-bacnet-stacks-playground/discussions/5) |
| **Upstream Haystack client** | [rusty-haystack](https://github.com/jscott3201/rusty-haystack) |
| **Open-FDD consumer** | JSON API driver + MCP bench profile |

## What you are building

Project name: **`bas-haystack-lake-rs`**

```text
Niagara / JACE / nHaystack (read-only)
        │  private Tailscale / VPN
        v
Rust collector  →  Postgres BAS lake
        │              │
        │              +→ sanitized read-only API (Open-FDD)
        │              +→ admin API (pause/resume sites, audit log)
        └→ alerts (stale sites, poll failures)
```

## Non-negotiable safety rule

**Never write to the live BAS.** Allowlisted Haystack ops only: `about`, `ops`, `read`, `nav`, `hisRead`, and other explicitly read-only calls. Enforce with a wrapper that rejects forbidden operations before HTTP is sent.

## Workspace layout (target)

```text
bas-haystack-lake-rs/
  crates/   core, haystack_client, collector, api, admin, replicator, alerts
  migrations/
  docs/     ARCHITECTURE.md, SECURITY.md, OPENFDD_INTEGRATION.md, RUNBOOK.md
  scripts/  dev_smoke.sh, check_stale_sites.sh
  Dockerfile, docker-compose.yml
```

## Recommended order

1. Read [Discussion #5](https://github.com/bbartling/py-bacnet-stacks-playground/discussions/5) or paste [AGENTS.md](./AGENTS.md) into your coding agent.
2. Complete **Vibe Code 17** Haystack lab ([nhaystack-niagara-pi-tutorial](../vibe_code_apps_17/nhaystack-niagara-pi-tutorial/)) — Basic auth, not SCRAM.
3. Stand up mock Haystack + Postgres; implement collector `doctor` and `poll-once`.
4. Add admin pause/resume + audit log.
5. Ship sanitized `/v1/sites/:id/current` for Open-FDD flat JSON pull.
6. Document in `docs/OPENFDD_INTEGRATION.md` — lake feeds Open-FDD; FDD logic stays in Open-FDD.

## Open-FDD integration shape

Sanitized API default (from spec):

```json
{
  "site_id": "demo_site",
  "ts": "2026-06-25T00:00:00Z",
  "values": {
    "ahu1.sat": 55.2,
    "ahu1.fan_status": true
  }
}
```

No customer names, station hostnames, or raw Haystack URLs in responses.

## Related checkpoints

| # | Project |
| --- | --- |
| 12 | [Edge-to-cloud HVAC FDD pipeline](../vibe_code_apps_12/) — **Active** |
| 16 | [Rust BACnet stack lab](../vibe_code_apps_16/) — Open-FDD mimic, rusty-bacnet server/probe — **Active** |
| 17 | Project Haystack playground |
| open-fdd | Drivers, DataFusion SQL, MCP sidecar |

## Status

**Active** — agent prompt published; implementation tracked in this folder and Discussion #5.
