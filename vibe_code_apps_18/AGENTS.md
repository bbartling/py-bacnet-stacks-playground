# Agent prompt — build `bas-haystack-lake-rs`

**Paste this entire file** into Cursor, Codex, or another coding agent.

**Discussion:** [GitHub #5 — Agent prompt to build a DIY data lake](https://github.com/bbartling/py-bacnet-stacks-playground/discussions/5)

---

You are an expert Rust backend engineer, BAS/HVAC controls engineer, and security-minded platform engineer. Your mission is to build a production-quality all-Rust project for a **read-only** BAS / Haystack / Open-FDD data lake control plane. Do not stop at a sketch. Do not leave placeholder TODOs for core behavior. Iterate until the repository builds, tests pass, Docker runs, and the acceptance checkpoints below are complete.

## Project name

**`bas-haystack-lake-rs`**

## High-level purpose

Build a Rust service stack that can safely collect **read-only** telemetry from Niagara / JACE / nHaystack / Project Haystack endpoints over a **private VPN/Tailscale** network, store normalized point/current/history data in **Postgres**, expose a secure **admin API** for enabling/disabling sites, expose a **sanitized read-only current-values API** for Open-FDD, and provide operational health checks and stale-data alerts.

This is **not** a BAS write tool. It must never write to the control system. The only writes are to our own Postgres database.

## Non-negotiable safety rule

Every BAS/Haystack station interaction must be **read-only**.

**Allowed:** `about`, `ops`, `read`, `nav`, `hisRead`, other explicitly read-only Haystack operations.

**Forbidden:** writes, setpoint changes, command operations, priority-array writes, BACnet writes, anything that changes the live BAS.

Enforce with a read-only Haystack client wrapper that **rejects any non-allowlisted operation before the request is sent**.

## Architecture

```text
Niagara / JACE / nHaystack station
        │  private Tailscale / VPN only
        v
Rust collector service
        v
Postgres BAS lake
        +--> sanitized read-only API for Open-FDD / external tools
        +--> admin API for site enable/disable, status, onboarding
        +--> alerts for stale site connections and failed polls
```

## Required workspace layout

```text
bas-haystack-lake-rs/
  Cargo.toml
  README.md
  AGENTS.md
  LICENSE
  .gitignore
  .env.example
  Dockerfile
  docker-compose.yml
  migrations/0001_init.sql
  crates/
    core/
    haystack_client/
    collector/
    api/
    admin/
    replicator/
    alerts/
  scripts/
    bootstrap_cloud_vm.sh
    check_stale_sites.sh
    dev_smoke.sh
  docs/
    ARCHITECTURE.md
    SITE_ONBOARDING.md
    SECURITY.md
    OPENFDD_INTEGRATION.md
    RUNBOOK.md
  .github/workflows/
    ci.yml
    docker.yml
```

## Rust stack

Use modern idiomatic Rust. Prefer: **tokio**, **axum**, **tower**, **serde**, **sqlx**, **reqwest**, **tracing**, **thiserror**, **clap**, **uuid**, **time**, **argon2**, **jsonwebtoken**, **secrecy**, **dotenvy**.

Integrate **[rusty-haystack](https://github.com/jscott3201/rusty-haystack)** when possible. If its API does not support required Niagara interaction, isolate behind a `HaystackReadClient` trait with a reqwest fallback adapter.

## Core Postgres tables

`clients`, `sites`, `site_auth_secrets`, `points`, `current_values`, `history_values`, `polled_history`, `site_heartbeats`, `ingest_errors`, `admin_users`, `admin_api_tokens`, `audit_log`, `openfdd_exports`.

## Collector

```bash
cargo run -p collector -- doctor
cargo run -p collector -- poll-once --site <site_id>
cargo run -p collector -- run
```

Per enabled site: refresh points, poll current values, upsert, append COV snapshots, poll native history with watermarks, update heartbeat, record errors without killing other sites.

## Admin API (Axum)

Required routes include: `GET /health`, `GET /ready`, `POST /admin/login`, CRUD/pause/resume sites, `GET /admin/audit`. JWT or strong API tokens; Argon2 password hashes; **audit_log on every mutating action**.

## Sanitized Open-FDD API

Read-only: `GET /v1/sites`, `GET /v1/sites/:site_id/current`, points, history. **No** customer names, station names, IPs, hostnames, or credentials. Bearer token auth; rate limit.

Default flat JSON:

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

Document consumption in **`docs/OPENFDD_INTEGRATION.md`**. Open-FDD owns FDD/model/rules; this project **feeds** Open-FDD.

## Replicator & alerts

Replicator: incremental sync, dry-run, never sync admin secrets to public replicas.

Alerts: stale sites, consecutive failures, point-count drops, auth failures — webhook support, cooldown/suppression.

## Tests required

Unit + integration tests: read-only allowlist, COV deadband, stale detection, auth hashing, pause/resume, sanitized JSON shape, mock Haystack server.

## Acceptance checkpoints (definition of done)

- `cargo fmt`, `clippy -D warnings`, `cargo test`, `cargo build --release` pass
- `docker compose up --build` works; `/health` OK
- Collector `doctor` + mock Haystack poll writes Postgres
- Admin pause/resume; paused sites not polled; audit log written
- Sanitized API returns flat JSON without leaking URLs/IPs/customer names
- Alert checker flags stale site
- **No secrets committed; no station write operations; no core TODOs**

## Iteration rule

Implement the smallest complete vertical slice → test → fix → repeat until all checkpoints pass. Do not stop after generating files.

## Final deliverable

Summary, file tree, commands run, test results, local start instructions, first-site onboarding, pause/resume flow, security caveats, and explicit future work only for non-core items.
