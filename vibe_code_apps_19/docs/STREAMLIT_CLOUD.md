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

## Unified app (local + cloud)

One sidebar picker:

- **Folder** — local historian tree (hidden when `allow_server_paths` is false)
- **Zip package** — always available; uncached; **Clear session** wipe
- **AI agent / package help** expander — agent steps + limits

Disk saves (`configs/`) become **downloads** on shared/Cloud hosts.

## Honest limits

- One shared Python process for all visitors
- Session wipe is **best-effort**
- Not a security boundary for sensitive building data
- Keep zips ≤ 25 MB

## AI agents

Open the public URL → upload zip (+ optional `session_config.json`). No locked per-agent backend on Streamlit Cloud.
