# BAS agent skills — hard guardrails

Rules apply to every **`bas_build_spec/skills/<folder>/SKILL.md`** and optional `references/`, `scripts/`, `assets/`. Pattern matches [Phaser `skills/`](https://github.com/phaserjs/phaser/tree/master/skills) and OpenAI Codex “directory + SKILL.md” skills.

## Do

| Rule | Detail |
|------|--------|
| **One domain per folder** | Folder name = kebab-case task; `name` in frontmatter matches folder. |
| **YAML frontmatter** | `name` + rich `description` (triggers: BACnet, DOAS, VRF, Brick, trend, …). |
| **Link to repo sources** | `spec.md`, `bacnet_scripts.md`, `graphic.html` — do not paste the whole spec. |
| **Remote BAS URLs** | Document **`http://<server-lan-ip>:5173/`** (UI) and **`:8000`** for API when using the two-port layout — or one reverse-proxied origin per `bas_app/deploy/Caddyfile.example`. **Never** tell operators to use **`http://localhost:…`** from another PC (`localhost` is always the client machine). |
| **Real BACnet on wire** | Follow **`bacnet-driver-lifecycle`**: a **human** records sign-off on discovery (instances, addresses, expected object counts) in **`BUILD_CHECKPOINTS.md`** before automation claims a “live BACnet verified” slice or enables driver flags. |
| **Cross-link** | “Related skills” at bottom of each `SKILL.md`. |
| **Split when long** | Keep `SKILL.md` under ~500 lines; move tables to `references/*.md`. |
| **Edit in place** | Repeated fixes → update the same skill before splitting a new folder. |

## Do not

| Anti-pattern | Why |
|--------------|-----|
| Duplicate `spec.md` | Single source of truth. |
| One-off bug skills | Use commits + tests. |
| Vague `description` | Retrieval fails. |
| **>1** new or materially expanded skill folder per critique wake | See `bas_wake.sh` task 7. |
| Secrets in repo | No keys, passwords, or private station IPs. |
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
