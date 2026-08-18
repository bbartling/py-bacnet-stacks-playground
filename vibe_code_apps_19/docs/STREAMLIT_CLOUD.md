# Streamlit Community Cloud notes

## Deploy

1. Push `vibe_code_apps_19` (or set Cloud **app path** to this folder in the monorepo).
2. Streamlit Cloud → New app:
   - **Main file:** `streamlit_app.py`
   - **Python:** 3.11+
   - Dependencies: `requirements.txt` in this folder (Cloud installs that file)
3. Optional secrets / env:
   ```text
   APP_MODE=cloud
   ```
4. Users pick **Data source → Zip package** and upload `openfdd_package_v1` — see [PACKAGE_SPEC.md](PACKAGE_SPEC.md).

**No Dockerfile on Community Cloud.** The repo `Dockerfile` is for self-host / local parity only — see [DOCKER.md](DOCKER.md).

## Unified app (local + cloud)

One sidebar picker:

- **Folder** — local historian tree (hidden when `allow_server_paths` is false)
- **Zip package** — always available; uncached; **Clear session** wipe
- **Session restore (Cloud-safe)** — download / upload `session_config.json` (+ optional `fault_settings.json`)
- **AI agent / package help** expander — agent steps + limits

Disk saves (`configs/`) become **downloads** on shared/Cloud hosts.

## Multi-user session isolation

Each Streamlit browser session gets its own UUID workspace:

```text
{temp}/vibe19/{session_id}/package/   extracted zip
{temp}/vibe19/{session_id}/exports/   Engineering Findings DOCX/XLSX
```

- Dataset frames, mappings, rule results, and notes live in **`st.session_state`** only.
- **Clear session** deletes **this** session's directory. It does not touch another visitor.
- Stale-temp sweep skips the current session and never deletes the shared `{temp}/vibe19` parent.
- Cloud / GHCR (`cfg.is_cloud`, including `APP_MODE=cloud`) **does not** read or write `.last_browser_session.json`. A refresh or a second visitor cannot restore someone else's last upload.
- Local single-user mode may still restore the last zip after refresh via that pointer until **Clear session**.
- Agent `.last_agent_session.json` auto-load is **local**. On Cloud/GHCR it runs only when `VIBE19_BOOTSTRAP` is set explicitly.
- Disconnect / new Streamlit session: uploaded data is gone. Re-upload the zip (and optional `session_config.json`).
- Streamlit floor: **`>=1.51`**. Isolation does **not** require `st.cache_data(scope="session")` (Streamlit 1.53+).
- This is isolation between browsers on one process — **not** a cryptographic security boundary for highly sensitive BAS data.

## Session round-trip (Cloud-friendly)

Tuned mapping / thresholds are **not** persisted on the Cloud host. Use browser download/upload:

1. Upload building zip (`openfdd_package_v1`).
2. Map roles / tune rule params (sidebar + Mapping / Overview).
3. **Download session config** → `session_config.json` (`openfdd_session_v1`: `unit_system`, `prefer_web_oat`, `role_map`, `params`, plant toggles). Optionally download **fault settings** (`params` only).
4. Later session: upload the **same zip**, then **Upload session config** → Apply — restores into `st.session_state` (no server path).
5. Re-run rules.

Same controls live in the sidebar and on the **Export** tab. Local agents can still paste JSON paths when `APP_MODE=local`.

## Honest limits

- One shared Python process for all visitors
- Session wipe is **best-effort**
- Not a security boundary for sensitive building data
- Keep zips within **two-tier** defaults:
  - Browser: `.streamlit/config.toml` → `server.maxUploadSize = 500` (stock Streamlit says “200MB per file” without this)
  - Agent/CLI/path: package_io **2048 MB** (`DEFAULT_PACKAGE_MB`) — prefer path load / `agent_afdd` for large buildings
  - See [PACKAGE_SPEC.md](PACKAGE_SPEC.md) / [DOCKER.md](DOCKER.md)
- Sidebar / Overview show loaded size vs package limit.

## AI agents

Open the public URL → upload zip → tune → download `session_config.json` for the next visit. No locked per-agent backend on Streamlit Cloud. Headless: `scripts/agent_afdd.py` + optional `session_config` / `fault_settings` in the export bundle.

Self-host image: [DOCKER.md](DOCKER.md) / `ghcr.io/<owner>/vibe19` (GHCR stores the image; it does not host the app).
