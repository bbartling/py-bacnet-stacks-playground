# Branch reconciliation — Streamlit merge (2026-07-09)

## Current state (audit)

| Item | Value |
|------|-------|
| **Audit branch** | `streamlit-pandas-demo-vibe19` @ `2439b91` |
| **Default branch** | `develop` (`origin/HEAD` → `origin/develop`) |
| **Local branches** | `develop`, `stage4-finish-parity-and-tuning`, `streamlit-pandas-demo-vibe19` |
| **Remote branches** | `origin/develop`, `origin/stage4-finish-parity-and-tuning`, `origin/streamlit-pandas-demo-vibe19` |

## `stage4-finish-parity-and-tuning` vs `develop`

```text
git log develop..stage4-finish-parity-and-tuning  → (empty)
git log stage4-finish-parity-and-tuning..develop  → 63beffc Achieve BUILDING_100 full SQL parity at 0.5h tolerance.
```

**Verdict:** No unique commits on `stage4-finish-parity-and-tuning` versus `develop`. `develop` is **one commit ahead** (SQL parity closeout on the old Rust/FastAPI stack). Safe to treat stage4 as **merged/redundant** after Streamlit merge; delete locally/remotely only after PR lands.

Local `stage4-finish-parity-and-tuning` @ `1778363` is 1 commit ahead of `origin/stage4-finish-parity-and-tuning` @ `7eda12b` (unpushed OAT-METEO fix, already superseded by `develop` @ `63beffc`).

## `streamlit-pandas-demo-vibe19` vs `develop`

**4 commits** (207 files, −26k / +4.5k lines under `vibe_code_apps_19/`):

| Commit | Summary |
|--------|---------|
| `dc90725` | Replace Vibe19 with Streamlit pandas FDD demo after Open-FDD Rust port |
| `e14504b` | Update gitignore for Streamlit demo |
| `531e064` | Port full 50-rule pandas cookbook |
| `2439b91` | BUILDING_100 role mapping + completion plan |

**Removes:** `fdd_app/`, `rust_fdd_core/`, `sql_rules/`, `haystack_rdf/`, Docker deploy stack.

**Adds:** `streamlit_app.py`, `app/`, `configs/`, 50-rule catalog, BUILDING_100 validation scripts/docs.

**Verdict:** This is the **canonical App 19 direction**. Merge into `develop` with Streamlit branch winning all App 19 conflicts.

## Merge plan

1. `git checkout develop && git pull --ff-only origin develop`
2. `git checkout -b merge/streamlit-pandas-demo-vibe19`
3. `git merge --no-ff streamlit-pandas-demo-vibe19`
4. Run pytest + BUILDING_100 validation
5. Push + open PR to `develop`
6. After merge: delete `stage4-finish-parity-and-tuning` (local + remote) — no unique work
7. Keep `streamlit-pandas-demo-vibe19` until PR merged, then optional delete

## Test plan (post-merge)

```powershell
cd vibe_code_apps_19
python -m pip install -e ".[dev]"
python -m pytest -q
python scripts/generate_rule_configs.py
python scripts/validate_building100.py
streamlit run streamlit_app.py
```

**Expected:** 50 rules, BUILDING_100 48 equipment if data present, 0 ERROR rows, no Rust/FastAPI folders.

## Branches safe to delete (after Streamlit PR merge)

- `stage4-finish-parity-and-tuning` (local + remote)
- `streamlit-pandas-demo-vibe19` (optional, after merge)

## Do not delete

- `develop`
- `merge/streamlit-pandas-demo-vibe19` until PR merged
- `feature/vibe19-multisite-csv-sql-mapping` (next work)
