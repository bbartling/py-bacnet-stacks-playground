# BAS agent skills — hard guardrails

Rules apply to every **`bas_build_spec/skills/<folder>/SKILL.md`** and optional `references/`, `scripts/`, `assets/`. Pattern matches [Phaser `skills/`](https://github.com/phaserjs/phaser/tree/master/skills) and OpenAI Codex “directory + SKILL.md” skills.

## Do

| Rule | Detail |
|------|--------|
| **One domain per folder** | Folder name = kebab-case task; `name` in frontmatter matches folder. |
| **YAML frontmatter** | `name` + rich `description` (triggers: BACnet, DOAS, VRF, Brick, trend, …). |
| **Link to repo sources** | `spec.md`, `bacnet_scripts.md`, `graphic.html` — do not paste the whole spec. |
| **Remote BAS URLs** | Document **`http://<server-lan-ip>:5173/`** (UI) and **`:8000`** for API when using the two-port layout — or one reverse-proxied origin per `bas_app/deploy/Caddyfile.example`. **Never** tell operators to use **`http://localhost:…`** from another PC (`localhost` is always the client machine). |
| **Real BACnet on wire** | Follow **`bacnet-driver-lifecycle`**. **Commissioning head-end:** `BAS_BACNET_AUTO_COMMISSION=true` + workers; **Codex** may edit **`cron/jobs.json`** (all schedules), BACnet scripts, rough-in tree UI, and `.env` bind vars when implementing operator chat requests. Disable auto flag before production handoff. |
| **Cross-link** | “Related skills” at bottom of each `SKILL.md`. |
| **Split when long** | Keep `SKILL.md` under ~500 lines; move tables to `references/*.md`. |
| **Edit in place** | Repeated fixes → update the same skill before splitting a new folder. |

## Do not

| Anti-pattern | Why |
|--------------|-----|
| **Edit `bas_app/` from Cursor** | Generated application code is **Codex CLI** (and human ops) only. Cursor agents change **`bas_build_spec/`** — spec, skills, memory, cron, validation — then verify against acceptance criteria. |
| Duplicate `spec.md` | Single source of truth. |
| One-off bug skills | Use commits + tests. |
| Vague `description` | Retrieval fails. |
| **>1** new or materially expanded skill folder per critique wake | See `bas_wake.sh` task 7. |
| Secrets in repo | No keys, passwords, or private station IPs. |
| **Site-specific OT LAN in generic docs** | No job bind/NIC/device IPs in `spec.md`, `skills/`, or wake templates — only in **`PHASE_NOTEPAD.md`**, **`memory/integrations/bacnet.md`**, and generated state. Run **`bas_validate_site_agnostic.sh`**. |
| **Caddy / nginx / Apache on :80 “for convenience”** | Do **not** install or reconfigure system reverse proxies unless **BUILD_CHECKPOINTS** (or a human) explicitly asks for lab routing — they hijack **`http://<ip>/`** and confuse BAS dial-in. Prefer documented **`5173`/`8000`** or the repo **Caddyfile example** with ops sign-off. |
| **localhost in runbooks** | Do not describe remote workstation access as `localhost`; use **LAN IP**, **DNS name**, or **`/etc/hosts`** alias (see `web-app-bas` skill). |

## Who may author

| Actor | Budget |
|-------|--------|
| Human | Always; follow this file. |
| `gpt-5.5` critique | At most **one** new folder **or** one major expand per wake, per `skills/README.md`. |
| `gpt-5.4-mini` | No new folders unless BUILD_CHECKPOINTS explicitly requests it. |

## Verification

1. Symlinks under `~/.cursor/skills/` still resolve after edit.  
2. Narrow chat query retrieves the intended skill.  
3. If wrong skill fires, expand **`description`** triggers—not the body size.  
4. **Cursor validation** follows **`spec-validation`** and `acceptance_criteria.md` release gate; run `cron_codex/bin/bas_validate_automation.sh` and optional `bas_smoke_login.sh` — do not edit `bas_app/` to clear a failed check.

## Long-lived runtime (Codex + critique)

Passing unit tests alone does **not** prove remote operators can log in. **`BUILD_CHECKPOINTS.md`** defines a **Tier A** runtime gate (**Path A:** user systemd with **`XDG_RUNTIME_DIR`** when `/run/user/UID` exists; **Path B:** **`bas_app/scripts/`** + README when the wake shell has no user bus). **`systemd-live-dev`** documents both. Critique must not treat product slices as “shipped” while **`:8000`** is down — proof is **`ss` + `curl`**, not necessarily **`systemctl --user status`** from cron.
