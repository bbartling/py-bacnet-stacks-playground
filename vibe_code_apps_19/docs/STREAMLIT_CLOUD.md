# Streamlit Community Cloud notes

## Deploy

1. Push `vibe_code_apps_19` (or monorepo subdirectory) to GitHub.
2. In Streamlit Cloud → New app → set:
   - **Main file:** `streamlit_app.py`
   - **Python version:** 3.11+
3. Secrets / env:
   ```text
   APP_MODE=cloud
   ```
4. Users upload an `openfdd_package_v1` zip — see [PACKAGE_SPEC.md](PACKAGE_SPEC.md).

## What Cloud mode does

- Zip uploader + Load / Clear (no local folder path, no tkinter browse)
- Uncached package load (does **not** use `@st.cache_data` for uploads)
- Temp extract under `vibe19_*` + **Clear session** wipe
- Column-map “save” becomes **download** (no write into shared `configs/`)

## Honest limits

- One shared Python process for all visitors
- Session wipe is **best-effort** (no reliable disconnect hook)
- Not a security boundary for sensitive building data
- Concurrent users share CPU/RAM — keep packages small (≤25 MB zip)

## AI agents

An agent can open the public URL and upload a zip via the browser UI. Streamlit Cloud does **not** provide locked per-agent backends. For true isolation, use separate app deploys or a real multi-tenant API (out of scope).
