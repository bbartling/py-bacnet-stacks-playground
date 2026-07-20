# OpenFDD WattLab Studio

**WattLab Studio** turns a [Vibe 19](../vibe_code_apps_19/) WattLab dump + energy-use
package into an ESCO fuel dashboard, EnergyPlus twin/calibrate viewer, and ECM
capital plan.

Chat with **Codex / agents outside Streamlit** on the shared workspace folder.
Studio is the upload dropzone + results viewer.

## Run (Docker / GHCR)

**Always pull, then recreate** (same easy-button as vibe19):

```bash
docker pull ghcr.io/bbartling/vibe20:latest
docker stop vibe20 2>/dev/null; docker rm vibe20 2>/dev/null
docker run -d --restart unless-stopped -p 8520:8501 --name vibe20 \
  ghcr.io/bbartling/vibe20:latest
```

Open **http://localhost:8520** (or `http://<host-ip>:8520`). Vibe19 typically uses **8502**.

```bash
docker ps
docker logs -f vibe20
docker stop vibe20
```

Optional shared workspace with Codex on the host:

```bash
docker run -d --restart unless-stopped -p 8520:8501 \
  -v /home/ben/wattlab_workspace:/data \
  -e WATTLAB_STUDIO_WORKSPACE=/data \
  --name vibe20 ghcr.io/bbartling/vibe20:latest
```

## Run (local)

```bash
cd vibe_code_apps_20
pip install -e ".[studio]"
wattlab studio
# or: streamlit run studio.py --server.port 8520
```

Workspace default: `.artifacts/studio_workspace/` (`uploads/dump`, `uploads/energy`, `runs`, `reports`).

## Studio pages (4 only)

1. **Uploads** — `wattlab_dump_*.zip` (v3) + energy-use zip/folder (`campus.json` + bill CSVs + optional Haystack `column_map`)
2. **Fuel dashboard** — ESCO monthly tables, peer EUI bands, Open-Meteo HDD/CDD, gap-aware charts
3. **Twin / calibrate** — resolve profile, dry-run / Docker EnergyPlus, modeled vs bills, crosscheck vs ESCO proxies
4. **ECMs** — catalog Easy Buttons + measure sets + capital plan guardrails

## Pre-ship smoke

```bash
python scripts/smoke_studio.py
python -m pytest tests/test_studio_app.py -q
# with Studio on :8520:
python scripts/browser_smoke_vibe20.py --url http://localhost:8520 --screenshots .artifacts/browser/native
```

## Related docs

| Doc | For |
| --- | --- |
| [`AGENTS.md`](AGENTS.md) | Agent handbook + twin CLI |
| [`vibe20_agent_spec/`](vibe20_agent_spec/) | Data contract + Codex workspace rules |
| [`../vibe_code_apps_19/docs/COLUMN_MAP_JSON.md`](../vibe_code_apps_19/docs/COLUMN_MAP_JSON.md) | Haystack point → CSV header maps |
