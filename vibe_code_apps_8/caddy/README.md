# Caddy reverse proxy for BAS Lite (VOLTTRON)

Put **Caddy** on **port 80** (and optionally **443**) so operators hit a normal URL while VOLTTRON keeps its platform web on **8080** (e.g. `http://192.168.204.12:8080/index.html` plus your app at `/app8/`).

This pack does the following:

1. **Root redirect** — `http://<pi>/` → `http://<pi>/app8/index.html` (path is configurable via **`CADDY_APP_PREFIX`**, so `/app7` works the same way).
2. **Reverse proxy** — all other paths (including `/app8/api/...` and static assets) are forwarded to **`127.0.0.1:8080`** with `X-Forwarded-*` headers so the SPA and APIs behave as if they were accessed on the same host/port the browser used.
3. **Optional Basic Auth** — browser login enforced by Caddy before any traffic reaches VOLTTRON (bcrypt hash in env file, suitable for boot-time configuration).
4. **Optional TLS** — self-signed certificate pair on **443**, with **HTTP → HTTPS** redirect on 80.

## Files

| Path | Role |
|------|------|
| `env.example` | Copy to `/etc/default/caddy-bas-lite` on the Pi. |
| `scripts/render-caddyfile.sh` | Installed as `/usr/local/bin/bas-lite-render-caddyfile.sh`; reads the env file and writes `/etc/caddy/bas-lite.caddy`. |
| `scripts/gen-selfsigned-cert.sh` | Creates `/etc/caddy/ssl/bas-lite.{crt,key}` with OpenSSL. |
| `scripts/install-caddy-bas-lite.sh` | Apt-installs Caddy (Cloudsmith repo), installs scripts + systemd unit, disables stock `caddy.service` if it would steal port 80. |
| `systemd/caddy-bas-lite.service` | Separate unit name **`caddy-bas-lite`** so it does not fight the default Debian `caddy` package layout until you choose one. |

## Quick install (on the Raspberry Pi)

From a clone of this repo on the Pi:

```bash
sudo bash vibe_code_apps_8/caddy/scripts/install-caddy-bas-lite.sh
sudo nano /etc/default/caddy-bas-lite
sudo bas-lite-render-caddyfile.sh
sudo caddy validate --config /etc/caddy/bas-lite.caddy --adapter caddyfile
sudo systemctl enable --now caddy-bas-lite
```

Then open `http://<pi-ip>/` — you should land on the React app after the redirect.

## Boot-time knobs (`/etc/default/caddy-bas-lite`)

- **`CADDY_APP_PREFIX`** — `/app8` for App 8, `/app7` for App 7, etc. Must match the agent `route_prefix` in VOLTTRON.
- **`CADDY_UPSTREAM`** — default `127.0.0.1:8080` (VOLTTRON web).
- **`CADDY_BASIC_AUTH_ENABLE=1`** — turn on Basic Auth; set **`CADDY_BASIC_AUTH_USER`** and **`CADDY_BASIC_AUTH_HASH`** (bcrypt from `caddy hash-password --plaintext 'secret'`).
- **`CADDY_TLS_ENABLE=1`** — listen on **443** with **`CADDY_TLS_CERT`** / **`CADDY_TLS_KEY`**; port **80** redirects to HTTPS only.

After any change:

```bash
sudo bas-lite-render-caddyfile.sh
sudo systemctl reload caddy-bas-lite
```

## Self-signed TLS

```bash
sudo bash vibe_code_apps_8/caddy/scripts/gen-selfsigned-cert.sh '192.168.204.12'
```

Set `CADDY_TLS_ENABLE=1` and matching paths in `/etc/default/caddy-bas-lite`, render, validate, restart. Browsers will warn until you trust the cert or install your own CA.

## Caddy version note

Caddy **2.8+** renamed the directive to **`basic_auth`**. If `caddy validate` errors on unknown `basic_auth`, you are on an older binary: either upgrade Caddy or change that one word in the generated file to `basicauth` (legacy) and re-validate.
