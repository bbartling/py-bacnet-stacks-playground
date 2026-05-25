---
title: Web app features (reference)
nav_order: 6
---

# Web app features (reference)

Low-level description of each screen in **Vibe12 Cloud** (`apps/vibe12-web`), served from the **web Lambda** Function URL.

## Architecture

```text
Browser (React SPA)
    |  HTTPS same origin
    v
Lambda Function URL
    |-- GET /assets/*     static JS/CSS (Vite build)
    |-- GET /             index.html (SPA)
    |-- POST /api/auth/login
    |-- GET/POST /api/*   Python (DynamoDB, FDD engine)
```

Stack: **React 19**, **TypeScript**, **Vite**, **Plotly**, **CodeMirror** (Python), styling aligned with **Open-FDD desktop-ui**.

## Login

| Item | Detail |
|------|--------|
| Endpoint | `POST /api/auth/login` with `{username, password}` |
| Session | Bearer token in `sessionStorage` |
| Config | Lambda env `VIBE12_WEB_USER`, `VIBE12_WEB_PASSWORD`, `VIBE12_AUTH_SECRET` |
| Troubleshooting | Browser console prefix `[vibe12][api]`; add `?log=debug` for timing lines |

## Dashboard

| Feature | Behavior |
|---------|----------|
| Site / building | Top bar; drives all API queries |
| Latest °C / °F | From last point in readings response |
| FDD status chip | From `fdd_open` summary (after go-live) |
| History | 6–168 h lookback |
| Display unit | Imperial °F or metric °C for chart axis |
| Rolling average | 1–15 min server-side average series |
| Chart | Plotly line trace; auto-refresh ~30 s (silent) |
| API | `GET /api/readings?hours=&rolling_avg_minutes=&temp_unit=` |

## Rule Lab

| Feature | Behavior |
|---------|----------|
| Rule list | Dropdown of all rules; add/remove |
| Rename | ✎ edit name — **per rule** (does not change other rules) |
| Code editor | Python `evaluate()` with syntax highlighting |
| BRICK targets | Multi-select from live registry + model; hidden if empty |
| Test rule | `POST /api/playground/test-rule` — hours from UI |
| Save draft | `POST /api/fdd-rules` → DynamoDB `ts_ms=-2` |
| Write to database | `POST /api/playground/go-live` — chunked backfill |
| Console | Text output from test/go-live |
| API load | `GET /api/fdd-rules?site_id=&building_id=` includes `brick_scope_options` |

## Data model

| Feature | Behavior |
|---------|----------|
| Registry table | `GET /api/points/{site}/{building}` — all `series_id` rows from ingest |
| Export JSON | Open-FDD-shaped `{sites, equipment, points}` |
| Import JSON | `POST .../import` — preserve `metadata.external_ref` = series_id |
| Sync TTL | Inline Turtle projection (white panel, no popup) |
| LLM workflow | Export + rules → external AI → import validated JSON |

## System

| Feature | Behavior |
|---------|----------|
| Health | `GET /api/health` — numpy, batch sizes, deploy revision |
| Log hint | `localStorage.vibe12_log=debug` |

## Backend tables (conceptual)

| DynamoDB use | Key idea |
|--------------|----------|
| Telemetry | `device_id` = series_id, `ts_ms` = sample time |
| Point registry | Meta row per site/building listing all series |
| Custom rules | Meta row `ts_ms=-2` JSON rules array |
| FDD summary | Meta row `ts_ms=0` status + flags |

## Browser logging policy

- **Default:** `info` — API method, path, status, duration, request id.
- **Errors:** always logged with short body snippet.
- **Not logged:** full telemetry arrays, rule source code on success.
- **Debug:** `?log=debug` or `localStorage.vibe12_log=debug`.

## Build & deploy UI only

```bash
./scripts/build_web_ui.sh   # npm build → web_lambda/static/app
cd aws_cloud_pipeline && sam build && sam deploy
```

---

Related: [Master checklist](00-master-checklist.md) · [Edge deploy](edge-deploy.md) · [AWS SAM](aws-cloud-sam.md)
