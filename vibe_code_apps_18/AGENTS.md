# Agent prompt — harden `bas-haystack-lake-rs` (Vibe Code App 18)

**Paste this entire file** into Cursor / Codex against the
[`vibe_code_apps_18`](https://github.com/bbartling/py-bacnet-stacks-playground/tree/develop/vibe_code_apps_18)
spec (or an existing `bas-haystack-lake-rs` checkout).

**Upstream baseline:** [AGENTS.md](https://github.com/bbartling/py-bacnet-stacks-playground/blob/develop/vibe_code_apps_18/AGENTS.md) · [Discussion #5](https://github.com/bbartling/py-bacnet-stacks-playground/discussions/5)

**Why this revision exists:** A real Niagara → Postgres sandbox (TADCO-style) showed that “history” is easy to get wrong: native historian is sparse, equipment tags are often wrong, and analysts need a **polled COV table + regularized wide exports**, not only live snapshots. This prompt upgrades App 18 so the lake is robust for Open-FDD and human analysis.

---

You are an expert Rust backend engineer, BAS/HVAC controls engineer, and security-minded platform engineer.

Your mission: **revise and implement** the DIY BAS / Haystack data lake (`bas-haystack-lake-rs`) so it is production-robust for:

1. Read-only collection from Niagara / JACE / nHaystack over Tailscale/VPN
2. Correct **dual-history** storage (native vs polled)
3. Reliable **equipment identity** (path-based, not display-name tags)
4. Operator-friendly **site/point configuration** (not a fragile Excel-only workflow)
5. Sanitized **Open-FDD** current + history APIs
6. Data-quality signals (gaps, flatlines, stale sites)

Do not stop at docs. Implement schema, collector behavior, config pipeline, APIs, tests, and docs. Keep the **non-negotiable rule: never write to the live BAS**.

If starting from scratch (no checkout yet), build the full stack to this design. If a prior App 18 scaffold exists, **revise it** — do not leave the old “history is optional / snapshot-only” ambiguity.

---

## Non-negotiable safety (unchanged)

Every BAS/Haystack interaction is **read-only**.

**Allowed:** `about`, `ops`, `read`, `nav`, `hisRead`, and other explicitly read-only ops.

**Forbidden:** writes, setpoints, commands, priority-array writes, BACnet writes.

Enforce with a `HaystackReadClient` wrapper that **rejects non-allowlisted ops before HTTP is sent**. Unit-test the allowlist.

---

## Lessons that must shape the design

Treat these as hard requirements (learned from a live Niagara Postgres lake):

### 1. Two history tables — different jobs

| Table | Role | Who uses it |
| --- | --- | --- |
| `history_values` | Optional **native** station historian (`hisRead` / `has_his`) | Sparse; often zone temps only |
| `polled_history` | **Primary** lake history: collector COV snapshots of **all** enabled points on a schedule | Open-FDD, analysts, FDD training |

**Critical:** `has_his = false` does **not** mean “no history.” It only means the station is not trending that point natively. The collector must still write `polled_history`.

If you only implement native history, plant/AHU sensors will look “snapshot-only” and the product is wrong.

### 2. Join keys

- Points have a stable **bigint** `pk` (internal) and a text `external_id` / Haystack `id`.
- `polled_history.point_pk` → `points.pk` (**bigint**).
- `history_values` may join on external id **or** pk — pick one, document it, never mix.
- Never join history on display name (`dis`) or `equip_ref`.

### 3. Equipment identity = path, not tags

Niagara `equip_ref` / display prefixes are frequently **mis-tagged** (e.g. VAV boxes labeled `BOILERS_PUMPS`).

**Canonical equipment key** = segment of `slot_path` / Haystack `nav` path **before the leaf point**.

Examples:

- `.../LIBERTY_100_AHU_1/AHU1 DA-T` → equip `LIBERTY_100_AHU_1`, point `DA-T`
- `.../Floorplans/Fifth_Floor/VAV-514/SpaceTemp` → equip `VAV-514` (or floorplan path), not whatever `equip_ref` says

Store both:

- `points.equip_ref_raw` (vendor tag, untrusted)
- `points.equip_key` (derived from path, trusted)
- `points.slot_path` / `nav_path` (full path)

All grouping, Open-FDD keys, and exports use `equip_key` + sanitized point role/name.

### 4. Value encoding

- Numerics in `val` (`double precision`)
- Booleans in `val_bool`
- Consumers always read: `coalesce(val, val_bool::int::float)` (or typed JSON)
- Polled history is **COV-compressed**: only write a row when value changes beyond deadband **or** on heartbeat interval (e.g. force a sample every N minutes even if unchanged, so gaps are detectable)

### 5. Analyst / Open-FDD grids

COV alone is not analysis-ready. Provide a **materialized or on-read regularized view**:

- Fixed interval (default **15 minutes**)
- `ffill` then `bfill` within a query window
- Single `timestamp_utc` column + wide or long sanitized keys
- Document that ffill **holds last value across collector outages** (honest about invented continuity)

### 6. Data quality

Emit metrics / alerts for:

- Site stale (no successful poll)
- Poller gaps longer than `2 × poll_interval`
- **Flatline** points (nunique == 1 over long window) — e.g. dead CT reading 0 A forever
- Sudden point-count drops
- Auth failures

Do not pretend flatlines are “good data”; flag them.

---

## Configuration maintenance (Excel is optional, not the source of truth)

**Problem:** Operators want a spreadsheet; engineers need reviewable, automatable config.

**Design: layered config**

```text
Git (source of truth)
  config/sites/<site_id>.yaml     # connection, poll interval, enable flags
  config/mappings/<site_id>.csv   # optional Open-FDD key overrides, equip aliases
        │
        v  `collector config sync` / admin import
Postgres tables
  sites, points, point_aliases, openfdd_key_map
        │
        v  optional export for operators
Excel / CSV download from admin API (never required for collector to run)
```

### Site YAML (required shape)

```yaml
site_id: liberty_center          # sanitized public id (no customer legal name required)
enabled: true
poll_interval_secs: 900          # 15 min
cov_deadband:
  default: 0.05
  by_unit: { "°F": 0.1, "%": 0.5 }
force_sample_secs: 900           # write polled_history even if unchanged
haystack:
  # secrets ONLY via env / secret store refs — never inline passwords
  base_url_env: HAYSTACK_URL_LIBERTY
  username_env: HAYSTACK_USER_LIBERTY
  password_env: HAYSTACK_PASS_LIBERTY
point_filter:
  # optional allow/deny by path glob
  include_path_globs: ["**/LIBERTY_*", "**/Meter_*"]
  exclude_path_globs: ["**/Lighting/**"]
openfdd:
  # default key = "{equip_key}.{point_role_or_leaf}"
  # overrides only when needed
  key_overrides: []
```

### Optional mapping CSV (human-editable)

Columns:

```text
slot_path_glob,equip_key_override,openfdd_key,include,notes
```

Admin API:

- `GET /admin/sites/:id/config` — export YAML+CSV
- `POST /admin/sites/:id/config/import` — import CSV/YAML (validated, audited)
- `GET /admin/sites/:id/config.xlsx` — **optional** Excel export for operators (generated from Postgres, not a runtime dependency)

**Rules:**

- Collector boots from **Postgres** (synced from Git or admin import).
- Excel is a **convenience export/import**, not the only way to configure.
- Every import writes `audit_log`.
- Reject imports that would enable write ops or embed secrets in the file.

---

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
  config/
    sites/                    # site YAML (Git source of truth)
    mappings/                 # optional per-site CSV overrides
  migrations/
    0001_init.sql
    0002_polled_history_equip_key.sql   # evolve as needed
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
    CONFIG.md
    DATA_MODEL.md
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

Optional Excel export may use a **feature-flagged** dependency (e.g. `calamine` / `rust_xlsxwriter`); collector must run without it.

---

## Required Postgres schema (evolve migrations)

Keep existing App 18 tables, but **require** these semantics:

### `points`

| Column | Notes |
| --- | --- |
| `pk` | `bigserial` primary key |
| `site_id` | FK |
| `external_id` | Haystack/Niagara text id |
| `dis` | display name |
| `slot_path` / `nav_path` | **required** for equip derivation |
| `equip_ref_raw` | untrusted vendor tag |
| `equip_key` | derived, indexed |
| `point_role` | optional classifier (sat, oat, zone_temp, …) |
| `unit`, `kind` | |
| `has_native_his` | station historian flag |
| `enabled` | collector include flag |

### `current_values`

Latest snapshot: `point_pk`, `ts`, `val`, `val_bool`, `status`, `polled_at`.

### `polled_history` (**primary history**)

```sql
point_pk bigint not null references points(pk),
ts timestamptz not null,
val double precision,
val_bool boolean,
primary key (point_pk, ts)
```

Indexes: `(ts)`, `(point_pk, ts desc)`.

### `history_values` (native, optional)

Same value columns; watermark per point/site for `hisRead` incremental pull.

### Config / quality

- `point_aliases` (`point_pk`, `openfdd_key`, `source`)
- `ingest_errors`, `site_heartbeats`
- `data_quality_events` (`site_id`, `point_pk`, `kind`, `detail`, `ts`) — flatline, gap, etc.
- `clients`, `sites`, `site_auth_secrets`, `admin_users`, `admin_api_tokens`, `audit_log`, `openfdd_exports`

### Sanitization

Public APIs never return: customer legal names, station hostnames, Tailscale IPs, Haystack URLs, credentials, raw `equip_ref_raw` unless explicitly admin-only.

---

## Collector behavior (must implement)

```bash
cargo run -p collector -- doctor
cargo run -p collector -- config-sync          # Git/YAML → Postgres
cargo run -p collector -- poll-once --site <id>
cargo run -p collector -- run
cargo run -p collector -- backfill-native --site <id>  # optional hisRead
```

Per enabled site, each cycle:

1. Refresh point catalog (`read`/`nav`) → upsert `points`, recompute `equip_key` from path
2. Read current values → upsert `current_values`
3. **COV write to `polled_history`** (deadband + force_sample)
4. Optionally incremental `hisRead` → `history_values` for `has_native_his` points only
5. Update `site_heartbeats`
6. Run quality checks (gap/flatline) → `data_quality_events`
7. Record errors **without** stopping other sites

Paused sites (admin) are not polled; audit every pause/resume.

---

## APIs

### Admin (authenticated, audited)

Unchanged essentials: health, ready, login, site CRUD, pause/resume, audit.

**Add:**

- Config export/import (YAML/CSV/optional xlsx)
- `GET /admin/sites/:id/quality` — recent flatlines/gaps
- `GET /admin/sites/:id/points?equip_key=`

### Sanitized Open-FDD API (bearer token)

```http
GET /v1/sites
GET /v1/sites/:site_id/current
GET /v1/sites/:site_id/history?from=&to=&equip_key=&interval=15m&format=wide|long
GET /v1/sites/:site_id/points
```

**Current** (default flat JSON — keep App 18 shape):

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

Keys = `openfdd_key` from alias map, else `"{sanitized_equip_key}.{sanitized_leaf_or_role}"`.

**History** (new, required):

- Source: **`polled_history`** by default (`source=native` optional)
- `interval=15m` returns regularized grid (ffill/bfill)
- `format=long`: `ts, key, value`
- `format=wide`: `ts` + one column per key (cap column count; paginate by equip_key)
- Never leak paths/URLs; keys only

Document in `docs/OPENFDD_INTEGRATION.md`: lake feeds Open-FDD; FDD logic stays in Open-FDD.

---

## Replicator & alerts

Replicator: incremental sync, dry-run, never sync admin secrets to public replicas.

Alerts: stale sites, consecutive failures, point-count drops, auth failures, **flatlines**, **poller gaps** — webhook support, cooldown/suppression.

---

## Docs to update/add

| Doc | Content |
| --- | --- |
| `docs/ARCHITECTURE.md` | Dual history, equip_key derivation, COV vs grid |
| `docs/SITE_ONBOARDING.md` | YAML config, secrets via env, Tailscale, first poll |
| `docs/CONFIG.md` | Git vs admin import vs optional Excel |
| `docs/DATA_MODEL.md` | Table semantics, join rules, anti-patterns |
| `docs/OPENFDD_INTEGRATION.md` | Current + history contracts |
| `docs/RUNBOOK.md` | Stale site, flatline CT, gap after outage |
| `docs/SECURITY.md` | Read-only BAS, secret handling, sanitized API |

Update root `AGENTS.md` / `README.md` so future agents inherit this design (do not leave the old “history is optional” ambiguity).

---

## Tests required (add to App 18 list)

- Read-only allowlist rejects write op names
- `equip_key` derived from path even when `equip_ref_raw` is wrong
- COV deadband suppresses tiny noise; force_sample still inserts
- `polled_history` populated for points with `has_native_his = false`
- History API regularize: no NaNs inside window after ffill/bfill; fixed step
- Flatline detector fires for constant series
- Config import rejects embedded secrets
- Sanitized JSON has no hostname/URL/customer fields
- Pause/resume + audit log
- Stale-site alert fires when heartbeat exceeds threshold

---

## Acceptance checkpoints

- [ ] `cargo fmt`, `clippy -D warnings`, `cargo test`, `cargo build --release`
- [ ] `docker compose up --build`; `/health` OK
- [ ] Mock Haystack: `poll-once` writes `current_values` **and** `polled_history`
- [ ] Point with `has_native_his=false` still appears in `polled_history`
- [ ] Mis-tagged `equip_ref_raw` does not break `equip_key` grouping
- [ ] `GET .../history?interval=15m` returns gapless numeric series
- [ ] Admin config import/export works; optional xlsx export works
- [ ] Quality endpoint reports a synthetic flatline
- [ ] Sanitized API leaks no URLs/IPs/names
- [ ] **No secrets committed; no BAS writes; no core TODOs**

---

## Implementation order

1. Migrations: `points` path/equip_key columns, `polled_history`, `point_aliases`, `data_quality_events`
2. `equip_key` derivation unit tests
3. Collector COV → `polled_history` (force_sample + deadband)
4. Config sync from YAML; admin CSV import/export
5. History API (regularized)
6. Quality checks + alerts
7. Optional xlsx export (feature-flagged dependency)
8. Docs + CI green

## Iteration rule

Smallest vertical slice → test → fix → repeat until all checkpoints pass. Prefer correct data semantics over extra UI chrome.

## Final deliverable

Summary of changes vs original App 18, schema diff, commands run, test results, how to onboard a site with YAML (and optional Excel export), how Open-FDD pulls current vs history, and explicit non-goals (no BAS writes, no FDD rules inside the lake).
