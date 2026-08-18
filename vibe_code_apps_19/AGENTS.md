# Contributor notes — Vibe 19 public Streamlit OpenFDD app

Educational Streamlit + pandas lab for the pinned OpenFDD cookbook. No LLM runtime.

## Hard rules

1. **OpenFDD pin:** `open-fdd[reporting]==4.4.1` (62 diagnostics). Do not silently omit catalog rules.
2. **No LLM / API key** at Streamlit runtime. Mapping helper text (`--mapping-prompt`) is copy-paste only.
3. **Session isolation:** `{temp}/vibe19/{session_id}/` (PR #105). Cloud never reads/writes `.last_browser_session.json`. Wipe only the current session.
4. **ZIP ingest is fail-closed:** no nested zip expansion; streamed `ExtractionBudget`; browser compressed **150 MB**, expanded **500 MB**, single file **80 MB**, CLI/path **2048 MB**.
5. **Tests:** `python -m pytest -q` from `vibe_code_apps_19/` (skip huge fixtures with `-m "not optional_zip"`). Streamlit floor `>=1.51`.
6. **Docs as the current public app.** Git history is enough for removed agent bootstrap.

## Layout

| Path | Role |
| --- | --- |
| `streamlit_app.py` | Zip/folder upload, mapping wizard, rules, plots, RCx, export |
| `app/fdd_runtime.py` | Streamlit-free load / run / engineering bundle export |
| `app/package_io.py` | Safe `openfdd_package_v1` ingest |
| `app/session_workspace.py` | Per-browser temp workspaces |
| `scripts/vibe19_prepare_package.py` | Flatten, map, validate, zip, optional multi-part split |
| `docs/PACKAGE_SPEC.md` | Package contract + size caps |

Image: `ghcr.io/bbartling/vibe19:latest`.
