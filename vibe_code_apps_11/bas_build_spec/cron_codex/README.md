# Scheduled Codex runs for incremental BAS build

This folder contains a **bash wake script** plus documentation so `cron` (or `systemd` timers) can drive incremental work on the BAS head-end using the Codex CLI.

**Artifacts elsewhere:**

| Path | Purpose |
|------|---------|
| `bas_build_spec/spec.md` | Full specification |
| `bas_build_spec/acceptance_criteria.md` | Formal checklist (`[ ]` / `[x]`) |
| `bas_build_spec/BUILD_CHECKPOINTS.md` | Living queue + critique output (updated each wake) |
| `bas_build_spec/cron_codex/state/next_directions.md` | Optional long-form directions |
| `bas_build_spec/skills/` | **Repo-local** Codex/Cursor skills (`<topic>/SKILL.md`, optional `references/`) |
| `bas_build_spec/cron_codex/bin/bas_skills_link.sh` | Symlinks `bas_build_spec/skills/*` → `~/.cursor/skills/` for Cursor |
| `bas_build_spec/skills/GUARDRAILS.md` | Hard limits (one skill change per critique wake, no secrets) |

---

## Fire it up (first time)

```bash
CR="/home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/cron_codex"
cp -n "$CR/env.example" "$CR/.env"
chmod +x "$CR/bin"/*.sh

# Sanity (paths + codex presence)
"$CR/bin/bas_smoke.sh"
# If this prints bwrap / RTM_NEWADDR → set CODEX_DANGEROUSLY_BYPASS=true in .env (isolated host), then re-probe
BAS_CODEX_ENV_FILE="$CR/.env" "$CR/bin/codex_sandbox_probe.sh" || true

# One cheap wake: 1× mini + 1× critique (prefix wins over values inside .env)
MINI_INVOCATIONS_PER_WAKE=1 \
BAS_CODEX_ENV_FILE="$CR/.env" \
"$CR/bin/bas_wake.sh"

# Logs
ls -lt "$CR/logs" | head
```

Then tune `.env`, install cron from `crontab.example`, and set `MINI_INVOCATIONS_PER_WAKE` to a steady cap (often **2–5** with **hourly** cron; see **Hourly cadence** below).

**Repo-local Cursor skills:** after clone or when you add a skill folder:

```bash
chmod +x /home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/cron_codex/bin/bas_skills_link.sh
/home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/cron_codex/bin/bas_skills_link.sh
```

---

## Hourly cron (one wake per hour — easier on API limits)

**Goal:** at most **one** `bas_wake.sh` run per clock hour → you cap how often Codex runs at all.

1. In **`crontab.example`**, use the **`0 * * * *`** line (minute `0`, every hour). Only **one** active wake line should be uncommented.
2. In **`cron_codex/.env`**, pair hourly with a **small** mini cap, e.g.  
   `MINI_INVOCATIONS_PER_WAKE=2` or `3`  
   (each wake = up to that many **`gpt-5.4-mini`** `codex exec` calls **plus 1** **`gpt-5.5`** critique).
3. Keep **`MINI_ALLOW_EARLY_STOP=true`** so a short queue can **`touch`** `state/stop_mini_loop` and skip extra minis that hour.

**Rough ceiling (if every mini runs, no early stop):**  
~**24 × (N + 1)** Codex execs per day for mini+critique (e.g. N=2 → ~72 calls/day). Still confirm against the [Codex usage dashboard](https://chatgpt.com/codex/settings/usage).

---

## Boot the web app after each wake + dial in from your laptop

Codex can start or refresh a dev stack **after** it finishes, via **`POST_WAKE_HOOK`** in **`cron_codex/.env`** (shell snippet `bas_wake.sh` runs every wake).

**1) Put your real app path and command in `.env`**, for example:

```bash
# Docker Compose (API + UI listening on 0.0.0.0 inside compose file)
POST_WAKE_HOOK='cd /home/ben/my-bas-app && docker compose up -d --build'

# Or Vite dev server (must bind all interfaces)
# POST_WAKE_HOOK='cd /home/ben/my-bas-app/frontend && npm ci && npm run dev -- --host 0.0.0.0 --port 5173'

# Or uvicorn
# POST_WAKE_HOOK='cd /home/ben/my-bas-app/backend && . .venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8000'

# Default bas_app slice: keep uvicorn (:8000) + python http.server (:5173) up between wakes (nohup; idempotent)
# POST_WAKE_HOOK=/home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/cron_codex/bin/bas_post_wake_stack.sh
# POST_WAKE_STACK_RESTART=true   # optional: restart each wake to pick up backend changes (brief outage)
#
# If bas_post_wake_stack.sh skips for your tree, point POST_WAKE_HOOK at a Codex-owned script under bas_app/scripts/
# (see bas_app/README.md "Headless / cron" section) — same 0.0.0.0 bind requirement.
```

**`systemctl --user` from cron/Codex:** Wake shells often have **no** user D-Bus (`Failed to connect to bus: No medium found`). That does **not** mean units are wrong — see **`bas_build_spec/skills/systemd-live-dev/SKILL.md`** (`XDG_RUNTIME_DIR=/run/user/$(id -u)`, **`loginctl enable-linger`**, or **`bas_app/scripts/`** Path B). Proof of life is always **`ss` + `curl`** to **:8000** / **:5173**.

Your app **must** listen on **`0.0.0.0`** (not only `127.0.0.1`) or the host firewall will only see localhost.

**2) On the server, find its LAN IP:**

```bash
hostname -I | awk '{print $1}'
```

**3) From another PC on the same LAN (or VPN), open a browser:**

`http://<that-ip>:<port>/`  
Examples: `http://192.168.1.50:5173`, `http://192.168.1.50:8000`.

**4) If the page does not load:** open the port on the server (example with `ufw`):

```bash
sudo ufw allow 5173/tcp comment 'BAS dev UI'
sudo ufw status
```

**5) Security:** `0.0.0.0` exposes the port on every interface that can reach the host. Prefer **VPN** or **LAN-only** firewall rules; do not expose raw dev servers to the public internet.

---

## Runs after you close SSH?

| Mode | Survives SSH disconnect? |
|------|---------------------------|
| **Foreground** `bas_wake.sh` in your SSH session | **No** — dies with the session unless you use `tmux`/`screen`/`nohup`. |
| **`cron`** (user crontab or `/etc/cron.d`) | **Yes** — `cron` is a system daemon; next tick runs `bas_wake.sh` without you logged in. |
| **`systemd` timer** | **Yes** — same idea as cron. |

Install **one** of cron or systemd on the **same host** that has `codex` logged in and repo access. Ensure `PATH` in crontab includes `codex` (see `crontab.example` `PATH=` line).

---

## How often can you run `codex exec --model gpt-5.4-mini`?

Limits are **not fixed constants** in the CLI: they depend on your **ChatGPT / Codex plan**, **model**, and **task size** (token-based accounting is rolling out for some customer segments). Authoritative numbers are in OpenAI’s docs and your account dashboard.

### Published **local message** ranges per **rolling 5-hour window** (indicative)

From [Codex pricing — usage limits](https://developers.openai.com/codex/pricing) (tables under “What are the usage limits for my plan?”), **local messages** and **cloud tasks share the same 5-hour window**. Separate rows exist per model; **additional weekly limits may apply**.

| Plan (examples) | `gpt-5.4-mini` / 5h | `gpt-5.5` / 5h |
|-----------------|---------------------|----------------|
| Plus / Business | **60–350** | **15–80** |
| Pro 5x | **300–1750** | **80–400** |
| Pro 20x | **1200–7000** | **300–1600** |

API-key mode uses **usage-based billing** instead of these included message buckets (see same page, “API Key” table).

### What one “wake” costs in messages

Each wake runs **up to** `MINI_INVOCATIONS_PER_WAKE` separate `codex exec` calls with **`gpt-5.4-mini`**, then **1** `codex exec` with **`gpt-5.5`** (critique).

- **Cap, not a guarantee:** the loop is scheduled for that **maximum**. It will still run **all** of them unless **`MINI_ALLOW_EARLY_STOP=true`** (default) **and** the mini model creates **`cron_codex/state/stop_mini_loop`** when it believes no further mini-sized slice remains *this wake*—then remaining minis are skipped and critique runs immediately.
- **Default cap in `bas_wake.sh` / `env.example`:** **5** minis (gentler than 15). Raise to **10–15** when you intentionally want a “big push” wake.

Treat **each `codex exec` as at least one local message** for that model’s bucket ([Codex pricing](https://developers.openai.com/codex/pricing); confirm on the [usage dashboard](https://chatgpt.com/codex/settings/usage)).

**Rough Plus math (illustrative):**

| Cadence | Mini cap | Mini msgs / 5h (if all run) | Critique `gpt-5.5` / 5h |
|---------|----------|------------------------------|-------------------------|
| **Hourly**, cap **2** | 2 + 1 critique | ~10 mini (if 5 wakes in 5h) | ~5 critique |
| Every **15** min, cap **5** | 5 + 1 critique | ~100 mini (20×5) | ~20 critique |
| Every **30** min, cap **10** | 10 + 1 | ~100 mini (10×10) | ~10 critique |

Tune from your **actual** dashboard; weekly caps may bind before the 5h window.

**Tuning knobs:**

- **`MINI_INVOCATIONS_PER_WAKE`** — lower = less burst per wake; combine with more frequent cron if you want steady progress.
- **`MINI_ALLOW_EARLY_STOP=false`** — force every planned mini every wake (burns full quota even if idle).
- **`MIN_MINUTES_BETWEEN_WAKES`** — debounce overlap with manual Codex.
- **Cron spacing** — `*/20` or slower is a conservative default for Plus + critique every wake.

### Stopping cron when the project is “done”

**`gpt-5.5` does not run `crontab` itself.** Flow:

1. Set **`REMOVE_CRON_WHEN_COMPLETE=true`** in `.env`.
2. Critique (or you) marks **`acceptance_criteria.md`** so there are **no** remaining `- [ ]` lines — including **`## Release gate`** (HTTP smoke, log sanity, frontend build + console-clean sweep, **simulator-only BACnet** unless a documented lab flag is on, E2E data sweep). Do not rush: that section exists so “done” implies verified stability, not only feature checkboxes.
3. **`bas_wake.sh`** calls **`bas_remove_cron_marked.sh`** at wake **start** and **end** when the checklist is complete → crontab line with `# BAS_CODEX_WAKE` is removed, and **`state/DONE_AUTOMATION`** is written so later wakes exit silently.

To resume automation, delete **`state/DONE_AUTOMATION`** and re-add the crontab line (or set `REMOVE_CRON_WHEN_COMPLETE=false` while testing).

---

## Setup

1. **Install and log in to Codex CLI** on the machine that will run cron (`codex login` as that user).

2. **Copy env file:**

   ```bash
   cp /home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/cron_codex/env.example /home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/cron_codex/.env
   ```

   Edit `BAS_REPO`, `CODEX_CWD`, models, `MINI_INVOCATIONS_PER_WAKE`, sandbox, log paths. **Do not commit `.env`.**

3. **Make helper scripts executable:**

   ```bash
   chmod +x /home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/cron_codex/bin/bas_wake.sh \
     /home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/cron_codex/bin/check_acceptance_complete.sh \
     /home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/cron_codex/bin/bas_remove_cron_marked.sh \
     /home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/cron_codex/bin/bas_smoke.sh \
     /home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/cron_codex/bin/bas_skills_link.sh \
     /home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/cron_codex/bin/codex_sandbox_probe.sh
   ```

4. **Dry run once (foreground):**

   ```bash
   BAS_CODEX_ENV_FILE=/home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/cron_codex/.env \
     /home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/cron_codex/bin/bas_wake.sh
   ```

   Inspect `bas_build_spec/cron_codex/logs/wake-*.log`.

5. **Install cron** (example; adjust user and path):

   ```bash
   crontab -e
   # paste ONE line from crontab.example (hourly recommended for quota)
   ```

   Prefer a dedicated **service user** with minimal privileges if this ever runs on a shared server.

6. **Crontab marker (for self-removal):** the wake command line **must** include the text `# BAS_CODEX_WAKE` (or your custom `CRON_MARKER`) so `bas_remove_cron_marked.sh` can delete **only** that job and leave your other cron entries alone.

---

## Troubleshooting: `bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`

Codex’s Linux path uses **bubblewrap** for `codex exec`. On some servers (hardened kernels, LXC without nesting, or `user.max_user_namespaces=0`), **every shell step fails** with that error — the wake **ends**, but **no files change**.

**Probe (run on the server):**

```bash
chmod +x ~/bas_build_spec/cron_codex/bin/codex_sandbox_probe.sh
BAS_CODEX_ENV_FILE=~/bas_build_spec/cron_codex/.env ~/bas_build_spec/cron_codex/bin/codex_sandbox_probe.sh
```

**Fixes (pick one, best first):**

1. **Allow unprivileged user namespaces** (admin): e.g. `sudo sysctl kernel.unprivileged_userns_clone=1` and persist in `sysctl.d` (policy-dependent). **If `sysctl` already shows `= 1` but bwrap still fails**, the block is usually **LXC/Docker (no nesting), seccomp, or AppArmor** — not the sysctl knob alone.
2. **Try a looser sandbox** in `.env`: `CODEX_SANDBOX=danger-full-access` (re-run the probe).
3. **Dedicated build host / VM:** set **`CODEX_DANGEROUSLY_BYPASS=true`** in **`cron_codex/.env`** so `bas_wake.sh` passes **`--dangerously-bypass-approvals-and-sandbox`** (no bubblewrap). This is the practical fix when **`RTM_NEWADDR`** persists despite `unprivileged_userns_clone=1`. **Do not** use on shared production shells.

`bas_wake.sh` treats bypass as true for **`true` / `True` / `TRUE`** (case-insensitive).

Also ensure **`CODEX_CWD`** points at the repo root you intend (`/home/ben` in your log); the mini/critique use `-C "$CODEX_CWD"`.

---

## Live web app after each wake (`POST_WAKE_HOOK` + `0.0.0.0`)

See **Boot the web app after each wake + dial in** (above) for `POST_WAKE_HOOK` examples and browser URLs.

### Tear down Caddy / lab reverse proxies (optional)

When **Caddy (or nginx) on port 80** collides with BAS expectations, run **on the server** as root:

```bash
sudo bash /home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/cron_codex/bin/bas_strip_lab_web.sh
```

That script **stops** common units (**`caddy`**, **`nginx`**, **`apache2`** if installed), **`disable`s `caddy`** so it does not return after reboot, and **stops** **post-wake** **uvicorn** / **`http.server`** if PID files exist under **`cron_codex/state/`**. To **purge** the Caddy Debian package, uncomment the **`apt-get remove`** line inside the script. Codex should **not** run this without explicit human direction (see **`bas_build_spec/skills/GUARDRAILS.md`**).

---

## When acceptance is met: go silent (optional self-removing cron)

If **`REMOVE_CRON_WHEN_COMPLETE=true`** in `.env`:

1. After each wake, `bin/check_acceptance_complete.sh` checks **`bas_build_spec/acceptance_criteria.md`** for any remaining **`- [ ]`** checklist rows (lines that look like `- [ ]` at column start).
2. When **none** are left (everything checked `[x]`), `bas_wake.sh` calls **`bin/bas_remove_cron_marked.sh`**, which runs `crontab -l`, drops lines containing **`CRON_MARKER`** (default `BAS_CODEX_WAKE`), and reinstalls the rest. Your other cron lines are preserved if they do not contain that marker.
3. It writes **`cron_codex/state/DONE_AUTOMATION`**. On later invocations, **`bas_wake.sh` exits immediately** (no Codex, no hook) until you **delete `DONE_AUTOMATION`** to re-arm manual testing.
4. **`POST_WAKE_HOOK`** still runs once when shutdown triggers (so you can do a final `docker compose up` or similar).

**Caveats**

- Premature `[x]` marks make automation stop early; keep the checklist honest.
- If the crontab line **omits** the marker, removal is a no-op (see logs); fix the crontab and re-run.
- **systemd timers** are not auto-disabled by this flow; disable the timer unit yourself when the project is done.

---

## Operational notes

- **Locking:** `flock` on `BAS_CODEX_LOCK` prevents overlapping wakes if a run exceeds the cron period.
- **Debouncing:** `MIN_MINUTES_BETWEEN_WAKES` skips a wake if the last successful end was too recent.
- **Git:** `--skip-git-repo-check` allows `CODEX_CWD` without a `.git`; point `CODEX_CWD` at your real repo root when the BAS app lives in git.
- **Safety:** Default sandbox is `workspace-write`. `CODEX_DANGEROUSLY_BYPASS=true` is **not** recommended for unattended cron; use only in an isolated VM/CI — your bensserver case may require it for bwrap.
- **Models:** If `gpt-5.4-mini` or `gpt-5.5` is renamed in a future CLI, update `.env` to match `codex exec -m` supported IDs.

---

## systemd timer (alternative to cron)

Example unit pair (paths adjusted to your install):

`/etc/systemd/system/bas-codex-wake.service`

```ini
[Unit]
Description=BAS incremental Codex wake

[Service]
Type=oneshot
User=ben
WorkingDirectory=/home/ben
EnvironmentFile=/home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/cron_codex/.env
ExecStart=/home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/cron_codex/bin/bas_wake.sh
```

`/etc/systemd/system/bas-codex-wake.timer`

```ini
[Unit]
Description=Run BAS Codex wake hourly

[Timer]
OnBootSec=5min
OnUnitActiveSec=1h
Unit=bas-codex-wake.service

[Install]
WantedBy=timers.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now bas-codex-wake.timer
```

---

## References

- [Codex pricing & limits](https://developers.openai.com/codex/pricing)
- [Codex usage dashboard](https://chatgpt.com/codex/settings/usage)
- Example manual invocation (from `text_test/notes.md`): `codex exec --model gpt-5.4-mini --skip-git-repo-check --color never ...`
