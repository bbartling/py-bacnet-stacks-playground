# Cron & `bas_wake` — cheat sheet

## Workspace memory + cron (OpenClaw-style)

```bash
export CR=/home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/cron_codex
$CR/bin/bas_workspace_cli.sh memory list
$CR/bin/bas_workspace_cli.sh memory search bacnet
$CR/bin/bas_workspace_cli.sh wake-status
$CR/bin/bas_workspace_cli.sh cron list
$CR/bin/bas_workspace_cli.sh cron dry-run
$CR/bin/bas_workspace_cli.sh cron runs bas-wake-hourly
$CR/bin/bas_validate_cron_services.sh   # cron + scheduler + systemd + /health
$CR/bin/bas_validate_wake_pass.sh       # manual/scheduled wake: building vs snagged + checkpoints
$CR/bin/bas_validate_automation.sh     # both (full)
$CR/bin/bas_wake_prepare.sh            # dry-run: chat slice + pinned notepad (no Codex)
$CR/bin/bas_validate_wake_chat_slice.sh # assert slice has notepad + wake-window chat
$CR/bin/bas_validate_site_agnostic.sh  # no lab subnet in generic spec/skills
# Autonomous BACnet (commissioning head-end): BAS_BACNET_AUTO_COMMISSION=true in $CR/.env
$CR/bin/bas_bacnet_auto_commission.sh   # arm wire + one Who-Is (worker; no Codex)
```

Agent map: **`bas_build_spec/AGENTS.md`** · truncated injection: **`bas_build_spec/scratch/memory-bootstrap-latest.md`**.

---

# Cron & `bas_wake` — cheat sheet

Set these once in your shell (adjust if your home path differs):

```bash
export CR=/home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/cron_codex
export LEGACY=/home/ben/bas_build/cron_codex   # old tree; only if you still have logs/cron there
```

---

## How many “API” / Codex calls per wake?

Each scheduled **`bas_wake.sh`** run does:

| Phase | Count | What |
|--------|------:|------|
| **Mini** | up to **`MINI_INVOCATIONS_PER_WAKE`** | Separate `codex exec …` invocations (see **value in `$CR/.env`**; `env.example` defaults to **5**). |
| **Critique** | **0 or 1** | One `codex exec` after minis, unless **`SKIP_CRITIQUE_WHEN_CLEAN`** skips it (see README) or **`state/waiting_human`** skipped the whole wake. |
| **Typical max** | **`MINI_INVOCATIONS_PER_WAKE` + 1** | e.g. `5 + 1 = 6` Codex runs per wake. |
| **Human gate** | **0** (whole wake) | `touch $CR/state/waiting_human` → no minis, no critique until `rm`. |
| **Clean-tree skip** | **0 critique** | `SKIP_CRITIQUE_WHEN_CLEAN=true` in `.env` and porcelain-clean repos after minis → minis still run, critique skipped. |

**Early stop:** if **`MINI_ALLOW_EARLY_STOP=true`** and the model creates **`state/stop_mini_loop`**, remaining minis this hour are skipped → **fewer** minis, still **+1** critique **unless** `SKIP_CRITIQUE_WHEN_CLEAN` applies.

**Change the cap:** edit **`$CR/.env`** → **`MINI_INVOCATIONS_PER_WAKE`**, or override only for one manual run:

```bash
MINI_INVOCATIONS_PER_WAKE=1 BAS_CODEX_ENV_FILE=$CR/.env bash $CR/bin/bas_wake.sh
```

**Cron frequency × minis** = rough quota burn (e.g. hourly × 6 ≈ six Codex runs per hour at defaults).

---

## Validate cron settings

Run on the **same user** cron uses (often your login):

```bash
export CR=/home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/cron_codex

# 1) Is any BAS wake scheduled?
crontab -l | grep -nE 'bas_wake|BAS_CODEX|bas_build_spec' || echo "NO matching lines — cron is not driving bas_wake (only manual runs)."

# 2) Does the line point at your real script and .env?
crontab -l | grep bas_wake

# 3) Script and .env exist and are readable?
test -x $CR/bin/bas_wake.sh && echo "bas_wake: executable OK" || echo "bas_wake: NOT executable — chmod +x or use: bash $CR/bin/bas_wake.sh"
test -f $CR/.env && echo ".env: present"

# 4) Would automation silently no-op?
test -f $CR/state/DONE_AUTOMATION && echo "WARN: DONE_AUTOMATION exists — wakes exit immediately until you rm this file" || echo "No DONE_AUTOMATION flag"
```

**Interpret the cron line:** fields are `minute hour day month weekday command`. Example **`0 * * * *`** = minute **0** of **every** hour. The command must end with **`# BAS_CODEX_WAKE`** (or your `CRON_MARKER`) if you rely on self-removal.

---

## Validate Codex “API” calls per wake

**Configured cap (from disk, not env.example):**

```bash
grep -E '^MINI_INVOCATIONS_PER_WAKE=' $CR/.env
grep -E '^MINI_ALLOW_EARLY_STOP=' $CR/.env
```

Expected **maximum** Codex invocations that wake: **`MINI_INVOCATIONS_PER_WAKE + 1`** (minis + critique).

**Override vs `.env`:** `MINI_INVOCATIONS_PER_WAKE=1 bash …/bas_wake.sh` uses **1** for that wake only; **`grep $CR/.env`** can still show **3**. The critique line (“up to **N** planned mini…”) is the real **N** for that run.

**Count what actually ran** (after a wake, pick that log). Codex logs may contain NULs — use **`grep -a`** to avoid **binary file matches** and missed **`bas_wake end`**.

```bash
log=$(ls -t $CR/logs/wake-*.log | head -1)

grep -a -c '^--- mini ' "$log" || true
grep -a 'You are the CRITIQUE pass' "$log" | head -1
grep -a 'bas_wake end' "$log" | tail -1
```

Compare mini **count** to **N** from the critique line. **Total Codex runs** ≈ **minis + 1** (critique) when the wake completed.

**One-shot dry expectation** (no log parse): use **`.env`** or the **env prefix** you passed, then **`$N + 1`** max.

---

## Start / stop / modify cron

**See what is installed**

```bash
crontab -l
```

Look for a line ending in **`# BAS_CODEX_WAKE`** (required for self-removal scripts).

**Edit cron**

```bash
crontab -e
```

- **Stop:** comment the line with **`#`** at the beginning, or delete the line.
- **Start again:** uncomment **one** wake line, or paste from **`crontab.example`** (only **one** active schedule to avoid double wakes).
- **Change schedule:** edit the cron time fields (e.g. `0 * * * *` = hourly at :00). Path must stay **`…/bas_build_spec/cron_codex/bin/bas_wake.sh`** if that is your install.

**Remove only the BAS line (scripted)**

```bash
bash $CR/bin/bas_remove_cron_marked.sh
```

(Usually tied to acceptance-complete flow; see **`README.md`**.)

**Cron will not run** if **`state/DONE_AUTOMATION`** exists — delete that file to re-arm:

```bash
rm -f $CR/state/DONE_AUTOMATION
```

---

## Manual wake (foreground) + live log

**Start one wake** (cheap: 1 mini + critique):

```bash
MINI_INVOCATIONS_PER_WAKE=1 BAS_CODEX_ENV_FILE=$CR/.env bash $CR/bin/bas_wake.sh
```

Your terminal prints the **log path**, then goes quiet — **normal**.

**Follow the log** (second terminal):

```bash
tail -f "$(ls -t $CR/logs/wake-*.log | head -1)"
```

Stop **`tail`** with Ctrl+C when you see **`=== bas_wake end`**.

---

## Grep logs — quick health

**Current install (`bas_build_spec`) — last 20 wake markers / errors:**

```bash
grep -a -E 'bas_wake (start|end)|ERROR|codex: command not found' $CR/logs/wake-*.log 2>/dev/null | tail -20
```

**Newest log only — last 40 interesting lines:**

```bash
log=$(ls -t $CR/logs/wake-*.log 2>/dev/null | head -1)
grep -a -E 'bas_wake (start|end)|ERROR|codex: command not found|WARN:' "$log" | tail -40
```

**Legacy path** (if you still have old `~/bas_build/…` logs):

```bash
grep -E 'bas_wake (start|end)|ERROR|codex: command not found' $LEGACY/logs/wake-*.log 2>/dev/null | tail -20
```

---

## List newest logs

```bash
ls -lt $CR/logs | head -15
```

---

## Lock / “another wake running”

Only one wake holds **`/tmp/bas_codex_wake.lock`** (or **`BAS_CODEX_LOCK`** from `.env`). If a wake exits badly, rare stale lock — check no **`bas_wake`** / **`codex`** still running before deleting lock files.

---

## Full reset (spec + cron state + empty `bas_app`)

**After backup.** See **`README.md`** and **`bin/bas_redo_automation_state.sh --help`**.

```bash
bash $CR/bin/bas_full_reset.sh
```

Same as `bas_redo_automation_state.sh --nuke-bas-app --reset-checklists --i-am-sure --yes` (also clears BACnet sign-off checkboxes and `CODEX_ACCEPTANCE_COMPLETE`).

---

## One-page “START AGAIN”

```bash
export CR=/home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/cron_codex
MINI_INVOCATIONS_PER_WAKE=1 BAS_CODEX_ENV_FILE=$CR/.env bash $CR/bin/bas_wake.sh
# other terminal:
tail -f "$(ls -t $CR/logs/wake-*.log | head -1)"
```

Longer walkthrough: **`TUTORIAL.md`**.
