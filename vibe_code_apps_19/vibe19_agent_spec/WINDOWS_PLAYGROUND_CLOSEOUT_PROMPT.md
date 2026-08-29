# Windows Cursor prompt — close out `py-bacnet-stacks-playground`

Paste this as the session brief on the **Windows** machine. Repo: `https://github.com/bbartling/py-bacnet-stacks-playground`. Base branch: **`develop`**.

**Do not patch Open-FDD Rust/SQL/DataFusion.** That work is a separate bensbench / GHA plan (`econ_damper_cast_0c100`). Windows owns vibe apps, vibe19 GHCR, and playground hygiene.

**Do not** `docker build` Open-FDD or vibe19 on bensbench (low RAM). After you publish GHCR, Linux only `docker pull ghcr.io/bbartling/vibe19:latest`.

Never edit Synthetic-59 `expected_faults.csv` or OpenFDD goldens.

---

## Already closed (do not reopen)

| Item | State |
| --- | --- |
| Vibe19 Prompt 2 (vav/mech/motor CSVs in dump) | Merged **PR #92** `4b710616` — `open-fdd[reporting]==4.4.1`, `dump_tables` in diagnostic/forensic bundles |
| Bool-quantile `agent_afdd` export crash | Prior vibe19 prompt; do not re-litigate unless `agent_afdd --export-profile summary` still rc≠0 |
| Open-FDD ECON-1/2 B100 0–100 damper | **OpenFDD SQL**, not vibe19. Pandas on 4.4.1 is the oracle. Do not “fix” B100 by changing pandas thresholds to match SQL |

---

## Goal

Leave playground **turnkey**: no leftover product patches, one or zero open PRs, no stale remote branches, failed Actions cleaned, `develop` green, vibe19 image pullable.

### 1. Hygiene first

```powershell
cd C:\Users\ben\Documents\py-bacnet-stacks-playground   # or your clone
git fetch origin --prune
git checkout develop
git pull origin develop
gh pr list --state open --limit 30
gh run list --status failure --limit 40
git branch -r
```

- Work only from **`origin/develop`**. Do not commit a dirty Linux checkout (bensbench has local `lessons/` / vibe-app deletes — ignore that tree).
- **Open PR today:** [#93](https://github.com/bbartling/py-bacnet-stacks-playground/pull/93) `fix/vibe22-postfix-pilot-readiness` — *Close Vibe22 RL POC evidence without a long campaign*. CI `vibe22-ci` + CodeRabbit were green; CodeRabbit posted **12 nits**. Address still-valid nits **on that branch**, then squash-merge, **delete the branch**.
- No other remote heads besides `develop` after #93 merges.
- Delete **historical failed** workflow runs (`gh run delete <id>`) so the Actions tab is not a graveyard. Do **not** cancel in-flight GHCR (`vibe19-ghcr` / `vibe20-ghcr` / `vibe22` image publish). Do not delete successful publishes.

### 2. Vibe22 (#93) closeout

- Scope stays **vibe_code_apps_22** RL POC evidence / fail-closed eval. No long training campaign. No Lakeside hardcoded ids.
- Keep tests passing: `vibe22-ci`.
- After merge: if a vibe22 image workflow exists, wait for green publish. Do not claim RL is production DSM.

### 3. Vibe19 — verify only, patch only if broken

On `develop` after #92:

1. Pin remains `open-fdd[reporting]==4.4.1`.
2. `dump_tables` still writes `vav_health_matrix.csv`, `mech_cooling_oat_bins.csv`, `motor_hours.csv`, `motor_weekly.csv` into diagnostic **and** forensic dumps / Engineering Bundle `MANIFEST.json`.
3. `python -m pytest -q` in `vibe_code_apps_19` (or `scripts/run_tests_local.ps1` if temp locks).
4. If GHCR `:latest` / `:develop` is behind `develop`, rebuild **QEMU multi-arch** `linux/amd64` + `linux/arm64` (`workflow_dispatch` `no_cache=true` if tags point at missing blobs). Spec: `vibe_code_apps_19/vibe19_agent_spec/AGENTS.md` rules 25 and 30.
5. Reply to Linux with: merge SHA, image digest (`docker buildx imagetools inspect ghcr.io/bbartling/vibe19:latest`), `open_fdd.__version__`.

If dumps already include those four CSVs and tests are green: **no vibe19 code PR**.

### 4. Other vibe apps

Only patch if `gh pr list` or failed **current** `develop` workflows show a real break. Do not revive vibe12/vibe20 historical red jobs from July unless `develop` tip is red.

### 5. Done when

- Zero open PRs (or only a brand-new follow-on you just opened with a reason).
- Remote branches = `develop` (+ `HEAD`).
- No failed runs on the recent Actions list (historical failures deleted).
- Vibe19 `:latest` digest posted for bensbench `docker pull`.
- Short note in `vibe_code_apps_19/vibe19_agent_spec/SESSION_LOG.md` (and vibe22 session/audit if #93 merged) — no Open-FDD SQL edits.

### Out of scope

- `bbartling/open-fdd` DataFusion SQL, `sql_rules/economizer_fault.sql`, cargo, OpenFDD GHCR
- Editing `expected_faults.csv`
- Local docker/cargo on the Linux bench
- Mass `ELSE 1` FDD changes
