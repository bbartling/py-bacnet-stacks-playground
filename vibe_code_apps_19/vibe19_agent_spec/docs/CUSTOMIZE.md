# Make it your own (~90% template)

App 19 is an **educational fork template**: keep the 50-rule cookbook + Streamlit shell, swap **data ingest**, **branding**, and **extra faults**. This doc is the agent/human map — architecture and hooks only (no full DB connectors shipped).

**Companion:** [`TEMPLATE.md`](../TEMPLATE.md) (greenfield CSV workflow) · [`CUSTOM_RULES.md`](CUSTOM_RULES.md) (extra faults)

---

## Canonical vs fork points

| Keep (canonical) | Fork / replace |
| --- | --- |
| 50 cookbook rules in `app/rules/cookbook_catalog.py` + `runner.py` operational gates | Thresholds / params via `session_config` / sidebar; **extra** faults as `CUSTOM-*` only |
| `openfdd_package_v1` contract (`docs/PACKAGE_SPEC.md`) as the **in-memory shape** | How bytes arrive: zip, folder, or **your DB loader** |
| Role map + column_map → cookbook roles | Your historian column names |
| Agent API export shape (`agent_api.py` / `agent_afdd.py`) | Deploy host (Docker vs Streamlit Cloud) |
| Package size caps (`package_io.effective_package_caps`) | Env overrides; branding assets |

**Never silently drop a canonical rule** — skip with `SKIPPED_*` / `NOT_APPLICABLE_*`. Do not re-add Rust / FastAPI / Haystack RDF.

---

## Key paths (start here)

| Path | Role |
| --- | --- |
| `streamlit_app.py` | UI entry: hero, sidebar load, tabs, session restore |
| `app/package_io.py` | Safe zip/dir ingest → `PackageLoadResult` (frames + role_map attrs + report) |
| `app/agent_api.py` + `scripts/agent_afdd.py` | Headless load / run / export (Streamlit-free) |
| `app/bootstrap.py` | Agent → Streamlit handoff (`.last_agent_session.json` / `VIBE19_BOOTSTRAP`) |
| `app/rules/custom_rules.py` | **Append** `CUSTOM-*` rules here |
| `app/rules/custom_boilerplate.py` | Templates + examples |
| `app/rules/custom_registry.py` | Merges custom into active catalog (canonical 50 untouched) |
| `shared/branding.py` | `APP_TITLE` |
| `assets/image_new_chiller.png` | Hero image |
| `docs/PACKAGE_SPEC.md` | Zip layout + **500 MB** default caps |
| `docs/STREAMLIT_CLOUD.md` / `docs/DOCKER.md` | Deploy paths |

---

## 1) Wire historian / live data → Postgres or SQL Server

**Goal:** replace zip/folder ingest with a loader that still yields the **same** contract the rest of the app expects:

```text
frames: dict[str, pd.DataFrame]   # equipment_id → wide history, DatetimeIndex UTC
weather: pd.DataFrame | None      # optional; wx_oa_t / oa_t
role_map / column_map             # cookbook roles → column names
df.attrs: equipment_id, building_id, poll_seconds, …
```

### Pattern (do not invent a second rules engine)

1. **Query** historian (read-only) → one wide DataFrame per equipment (or pivot long→wide).
2. **Normalize** timestamps with `app.data_loader.normalize_timestamp` (column `timestamp_utc`).
3. **Attach attrs** the same way `package_io.load_package_from_dir` does.
4. **Commit** into Streamlit session the same way `_commit_package_result` / `_commit_frames` do — or return a `PackageLoadResult`-like object for `agent_api`.

### Extension points / hooks

| Hook | Today | Your change |
| --- | --- | --- |
| Sidebar data source | Folder \| Zip in `streamlit_app._load_data` | Add e.g. “Postgres” / “SQL Server” radio + connection UI |
| Existing SQL helpers | `app/sql_sources.py` (SELECT-only SQLite / DuckDB / optional SQL Server) | Reuse `validate_readonly_sql` + `load_sqlserver_query`; reshape to equipment dict |
| Spec notes | `docs/SQL_SERVER_INPUT_GUIDE.md`, `docs/MULTI_SITE_CSV_SQL_SPEC.md` | Site-specific connection / view SQL |
| Headless | `agent_api.load_*` | Add `load_from_db(...)` that builds frames then calls the same run/export path |
| Safety | `package_io` size caps for zip | For DB, apply your own row/time-window limits; still show size estimate in UI if useful |

**Do not** implement production connection pools, write-back, or multi-tenant auth in this demo template unless the fork explicitly needs them.

---

## 2) Logo / branding / hero

| Piece | File |
| --- | --- |
| App title | `shared/branding.py` → `APP_TITLE` |
| Hero image | Replace `assets/image_new_chiller.png` (or change `_HERO_IMG` in `streamlit_app.py`) |
| Page chrome | `st.set_page_config` + `_render_app_hero()` in `streamlit_app.py` |
| Copy | Hero markdown under the title (workflow blurb) |

Keep Plotly `displaylogo: False` in charts unless you intentionally brand charts.

---

## 3) Different / extra faults

1. Copy a template from `app/rules/custom_boilerplate.py`.
2. Append to `CUSTOM_RULES` in `app/rules/custom_rules.py` — ids **must** start with `CUSTOM-`.
3. Optional gate in `operational_gate.py` under the same id.
4. Spec: [`CUSTOM_RULES.md`](CUSTOM_RULES.md). Tests: `tests/test_custom_rules.py`.
5. Overview shows `50 (+N custom)` when extras are loaded.

Env shortcut for examples: `VIBE19_INCLUDE_EXAMPLE_CUSTOM_RULES=1`.

---

## 4) Session restore · Docker · Streamlit Cloud

| Path | How |
| --- | --- |
| **Local / agent** | Folder or zip path; optional `VIBE19_BOOTSTRAP` / `.last_agent_session.json` auto-load |
| **Cloud-safe restore** | Upload zip → tune → **Download session config** → later upload **same zip** + **Upload session config** (no server disk). Sidebar + Export. |
| **Streamlit Community Cloud** | Main file `streamlit_app.py` + `requirements.txt`; set `APP_MODE=cloud` optional. **No Dockerfile.** See `docs/STREAMLIT_CLOUD.md`. |
| **Docker self-host** | `docs/DOCKER.md` — `docker build -t vibe19 .` then `docker run -p 8501:8501 -e APP_MODE=local vibe19` |

Package safety default: **500 MB** zip and expanded (`OPENFDD_MAX_*` overrides). Sidebar / Overview show loaded size vs limit.

---

## 5) Suggested agent checklist for a site fork

- [ ] Data arrives as equipment DataFrames + role_map (zip **or** DB loader)
- [ ] Branding title + hero asset updated
- [ ] Site-specific faults only as `CUSTOM-*` (canonical 50 intact)
- [ ] Session restore documented for your deploy target
- [ ] `python -m pytest -q` (or `scripts/run_tests_local.ps1`) green
- [ ] Append `SESSION_LOG.md` for non-trivial changes
