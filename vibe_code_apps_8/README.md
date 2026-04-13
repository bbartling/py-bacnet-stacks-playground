# Vibe Code App 8 — BAS / BMS Lite (React + VOLTTRON)

**Enhanced upgrade** from App 7: same **BACnet / Platform Driver / setpoint** edge story, with a **TypeScript React** UI compiled into the agent `webroot`, extra **operator APIs**, optional **Caddy** on port 80, and the **OAT share** supervisory agent. It is **not** a byte-for-byte copy of `vibe_code_apps_7` — see **`docs/bas-lite-app8-tutorial.md` §1.1** for lineage. **§8** of that tutorial inlines **systemd**, **journald / RAM logging**, and **SD card** guidance (merged from the App 7 bosspi ops doc) so App 8 stays self-contained.

## What ships here

- **`volttron_data/ben_bacnet/app8_web_agent/`** — VOLTTRON web agent (`ben.app8.web`, route prefix `/app8`).
- **`volttron_data/ben_bacnet/oat_share_agent/`** — supervisory **OAT / shared sensor** agent (`ben.oat.share`): default **15-minute** read + multi-target write via Platform Driver (`get_point` / `set_point`). See tutorial §4 (OAT share).
- **`frontend/`** — React app; production build writes to the agent `webroot/` (see `vite.config.ts`).
- **`deploy-app8-to-bosspi.ps1`** — copy agent tree to the Pi and install or restart the agent. Parameters: `-SshTarget`, `-RemoteVolttronRoot`, `-RemoteVolttronHome`, `-LocalAgentRoot`.
- **`deploy-oat-share-to-bosspi.ps1`** — same for `oat_share_agent` (same parameters).
- **`caddy/`** — optional **reverse proxy on port 80** (and **443** with TLS): root URL redirects into `/app8/`, proxies to VOLTTRON on **8080**, optional **Basic Auth** and **self-signed TLS** via `/etc/default/caddy-bas-lite` at boot. See **`caddy/README.md`**.

## Branding

Operator UI is labeled **BAS Lite** / **BMS / BAS Lite** to match the App 7 “bench lite” posture, not Open-FDD product chrome.

## Build the SPA (required before deploy)

```powershell
cd C:\Users\ben\Documents\py-bacnet-stacks-playground\vibe_code_apps_8\frontend
npm install
npm run build
```

This runs `tsc -b` and `vite build`, emitting static files under:

`vibe_code_apps_8/volttron_data/ben_bacnet/app8_web_agent/app8_web_agent/webroot/`

## Local dev against a live Pi (optional)

```powershell
cd frontend
$env:VITE_DEV_PROXY_TARGET="http://192.168.204.12:8080"
npm run dev
```

Open the URL Vite prints; API calls under `/app8/api/*` proxy to the Pi.

## Pi URLs

- UI: `http://<pi>:8080/app8/index.html` (or `/app8/` depending on platform routing)
- Health: `http://<pi>:8080/app8/api/health`

## Docs

- `docs/bas-lite-app8-tutorial.md` — dev preview, deploy, **Caddy** (port 80 / TLS / Basic Auth), BACnet / Platform Driver cheat sheet, SD/systemd notes, OpenClaw context.
- `docs/replicate-any-building-lan-topology.md` — portable site model JSON, driver identity naming, deploy script parameters, go-live checklist (any building / OT LAN).
- `caddy/README.md` — operator quick reference for the Caddy pack.
