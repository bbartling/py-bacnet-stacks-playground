# Vibe Code App 18 — DIY BAS / Haystack data lake (Rust)

**Active featured build.** Spec-driven, **read-only** Rust control plane for collecting Niagara / JACE / nHaystack telemetry into Postgres, serving sanitized **current + history** to **Open-FDD**, and operating sites over a private VPN/Tailscale network.

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
        │              +→ sanitized /v1 current + history (Open-FDD)
        │              +→ admin API (pause/resume, config import/export, quality)
        └→ alerts (stale sites, gaps, flatlines, poll failures)
```

## Design lessons (must implement)

Learned from a live Niagara → Postgres sandbox — do **not** ship snapshot-only:

| Requirement | Why |
| --- | --- |
| **Dual history** | `history_values` = optional native `hisRead`; **`polled_history`** = primary COV lake for **all** enabled points |
| **`has_his = false` ≠ no history** | Station may not trend plant/AHU points; collector still writes `polled_history` |
| **`equip_key` from path** | Niagara `equip_ref` is often wrong; derive equipment from `slot_path` / `nav` before the leaf |
| **YAML config in Git** | Source of truth; Excel/CSV is optional admin export/import only |
| **Regularized history API** | COV alone is not analysis-ready; `interval=15m` with ffill/bfill for Open-FDD |
| **Data quality** | Flag gaps, flatlines (dead CTs), stale sites — do not pretend constant 0 A is good data |

## Non-negotiable safety rule

**Never write to the live BAS.** Allowlisted Haystack ops only: `about`, `ops`, `read`, `nav`, `hisRead`, and other explicitly read-only calls. Enforce with a `HaystackReadClient` wrapper that rejects forbidden operations before HTTP is sent.

## Workspace layout (target)

```text
bas-haystack-lake-rs/
  config/sites/     # site YAML (Git source of truth)
  config/mappings/  # optional Open-FDD key / equip overrides
  crates/           # core, haystack_client, collector, api, admin, replicator, alerts
  migrations/       # points equip_key, polled_history, data_quality_events, …
  docs/             # ARCHITECTURE, CONFIG, DATA_MODEL, OPENFDD_INTEGRATION, RUNBOOK, …
  scripts/          # dev_smoke.sh, check_stale_sites.sh
  Dockerfile, docker-compose.yml
```

## Recommended order

1. Paste [AGENTS.md](./AGENTS.md) into your coding agent (or follow Discussion #5).
2. Complete **Vibe Code 17** Haystack lab ([nhaystack-niagara-pi-tutorial](../vibe_code_apps_17/nhaystack-niagara-pi-tutorial/)) — Basic auth, not SCRAM.
3. Migrations: `points` path/`equip_key`, `polled_history`, `point_aliases`, `data_quality_events`.
4. Collector: `config-sync` (YAML → Postgres), `poll-once` writes **current + polled_history** (COV + force_sample).
5. Admin: pause/resume, config import/export, quality endpoint.
6. Sanitized `/v1/sites/:id/current` and `/v1/sites/:id/history?interval=15m`.
7. Docs — lake feeds Open-FDD; FDD logic stays in Open-FDD.

## Open-FDD integration shape

**Current** (flat JSON):

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

**History** (required): `GET /v1/sites/:site_id/history?from=&to=&equip_key=&interval=15m&format=wide|long`

- Default source: **`polled_history`** (`source=native` optional)
- Keys = `openfdd_key` or `"{equip_key}.{leaf_or_role}"` — never paths, URLs, or customer names

## Site config (YAML, not Excel-only)

```yaml
site_id: liberty_center
enabled: true
poll_interval_secs: 900
force_sample_secs: 900
haystack:
  base_url_env: HAYSTACK_URL_LIBERTY
  username_env: HAYSTACK_USER_LIBERTY
  password_env: HAYSTACK_PASS_LIBERTY
```

Secrets only via env / secret store refs. Optional Excel export is generated from Postgres for operators — never required for the collector to run.

## Related checkpoints

| # | Project |
| --- | --- |
| 12 | [Edge-to-cloud HVAC FDD pipeline](../vibe_code_apps_12/) — **Active** |
| 16 | [Rust BACnet stack lab](../vibe_code_apps_16/) — Open-FDD mimic, rusty-bacnet server/probe — **Active** |
| 17 | Project Haystack playground |
| open-fdd | Drivers, DataFusion SQL, MCP sidecar |

## Status

**Active** — enhanced agent prompt (dual history, equip_key, YAML config, regularized history API, data quality). Implementation tracked in this folder and Discussion #5.
