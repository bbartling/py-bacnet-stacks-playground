# Codex wake — one command at a time

Run each block **in order**. Wait for each to finish before the next. Paths assume **`/home/ben/bas_build_spec`**; change if your tree differs.

---

## 0. Should I Ctrl+C?

- **`bas_wake.sh` looks frozen** — it usually is **not**. It sends **all output to a log file**, so your terminal stays quiet for **several minutes** while Codex runs.
- **Ctrl+C** stops the wake and the Codex run. That is **OK** if you meant to cancel; you may get a **half-updated** `BUILD_CHECKPOINTS.md`. It is **not** required just because you see no text.
- **Better:** open a **second** terminal and run the **tail** command in step 6 so you see live progress.

---

## 1. Go to the cron folder

```bash
cd /home/ben/bas_build_spec/cron_codex
```

---

## 2. Ensure `.env` exists (once per machine)

```bash
test -f .env && echo ".env ok" || cp -n env.example .env
```

If it printed nothing and created `.env`, edit it (editor of your choice) and set at least **`CODEX_CWD`**, **`BAS_REPO`**, and models if needed.

---

## 3. Confirm `codex` is installed

```bash
command -v codex
```

You should see a path (e.g. `/usr/local/bin/codex`). If empty, install/login to Codex CLI first.

---

## 4. Sanity check (optional but quick)

```bash
bash bin/bas_smoke.sh
```

---

## 5. Run **one** wake (foreground)

Use a **single short** wake the first time (`1` mini + critique):

```bash
MINI_INVOCATIONS_PER_WAKE=1 BAS_CODEX_ENV_FILE=/home/ben/bas_build_spec/cron_codex/.env bash bin/bas_wake.sh
```

Your terminal should print **two lines** with the **log file path**, then go quiet. **That is normal.**

---

## 6. In a **second** terminal — watch the log

Replace the path if step 5 printed a different file:

```bash
ls -t /home/ben/bas_build_spec/cron_codex/logs/wake-*.log | head -1
```

Then (paste the path you got, or use):

```bash
tail -f "$(ls -t /home/ben/bas_build_spec/cron_codex/logs/wake-*.log | head -1)"
```

Leave this running until you see **`=== bas_wake end`** in the log. Then Ctrl+C **only** the `tail` (not the first terminal unless you already stopped the wake).

---

## 7. After it ends — confirm exit

```bash
tail -5 "$(ls -t /home/ben/bas_build_spec/cron_codex/logs/wake-*.log | head -1)"
```

You want **`bas_wake end`** and no stuck Codex errors at the bottom.

---

## 8. Full reset (optional — destroys `bas_app`)

**Only after backup.** One line:

```bash
bash /home/ben/bas_build_spec/cron_codex/bin/bas_redo_automation_state.sh --nuke-bas-app --i-am-sure --yes
```

No second terminal needed; this one prints to the terminal.

---

## 9. Install cron (optional — later)

When manual wakes work, see **`crontab.example`** in this folder and **`README.md`** § Setup. Do **not** enable cron until one manual wake succeeds.

**Cron start/stop, how many Codex calls per wake, log greps:** **`CHEATSHEET.md`**

---

## Troubleshooting (one check at a time)

**No `wake-*.log` file**

```bash
ls -la /home/ben/bas_build_spec/cron_codex/logs
```

**Instant exit, no log**

```bash
test -f /home/ben/bas_build_spec/cron_codex/state/DONE_AUTOMATION && echo "Automation finished flag is set — delete this file to run wakes again" || echo "No DONE flag"
```

**`Lock busy` in log**

Another wake is using `/tmp/bas_codex_wake.lock`; wait or stop the other process.

**`codex not in PATH`**

Fix PATH in the shell you use for cron, or symlink `codex` into a directory that cron’s user PATH includes.
