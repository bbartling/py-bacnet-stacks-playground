# Dashboard contract (do not vibe-code away)

**Audience:** Cursor / Codex / any agent editing `vibe_code_apps_19`.

This Streamlit app is an **RCx + FDD review dashboard**, not a disposable demo. Features listed here are **product requirements**. Removing or silently renaming them without an explicit human decision + this doc update is a regression.

| Freeze source | Path |
| --- | --- |
| RCx preset ids | `app/rcx_plots.py` → `REQUIRED_RCX_PRESET_IDS` + `PRESETS` |
| UI sections + chart APIs | `app/dashboard_contract.py` |
| Plots cards + Generic RCx DOCX | [`PLOTS_DOCX_VALIDATION.md`](PLOTS_DOCX_VALIDATION.md) · `app/rule_card.py` · `app/docx_report.py` |
| Per-rule plot / Haystack / sliders | [`RULE_PLOT_CATALOG.md`](RULE_PLOT_CATALOG.md) (all 58) |
| Tests | `tests/test_rcx_presets.py`, `tests/test_rule_card.py`, `tests/test_docx_report.py` |
| UI | `streamlit_app.py`, `app/ui_rcx_tab.py` |
| Figures | `app/charts.py` |

---

## Non-negotiable RCx presets (full existing catalog)

**All** of these ids must remain in `PRESETS` (enforced by pytest). Empty data for a site is fine; deleting the preset is not.

### Reset / plant (highest priority)

| Preset id | Chart | What it shows | RCx question |
| --- | --- | --- | --- |
| `hw_reset_scatter` | scatter vs **web OAT** | Hot-water **leave / supply** (`hw_supply_t`) — boiler / HW plant | Is HW reset working with outdoor air? |
| `chw_reset_scatter` | scatter vs **web OAT** | Chilled-water **leave / supply** (`chw_supply_t`) — chiller / CHW plant | Is CHW reset working with outdoor air? |
| `cw_reset_scatter` | scatter vs **web wet-bulb** | Condenser / **tower** water (`cw_supply_t`) | Tower / CW reset vs wet-bulb? |
| `duct_static_box` | **box** (fan proven on) | AHU `duct_static` | Flat high static → duct-static **reset** opportunity |
| `ahu_sat_reset_scatter` | scatter vs **web OAT** | AHU discharge / leave-air (`sat`) | SAT reset with outdoor air? |

### Cohort overlays (also frozen)

| Preset id | Chart | Role |
| --- | --- | --- |
| `zone_temps` | timeseries | `zone_t` |
| `ahu_dats` | timeseries | `sat` |
| `ahu_mats` | timeseries | `mat` |
| `ahu_rats` | timeseries | `rat` |
| `ahu_dampers` | timeseries | `oa_damper_pct` |
| `vav_flows` | timeseries | `zone_flow` |
| `fan_speeds` | timeseries | `fan_cmd` |

Adding a **new** preset to `PRESETS` is allowed. Promoting it into `REQUIRED_RCX_PRESET_IDS` + this doc is required once it is part of the supported product.

---

## Main UI sections (lazy radio — not eager `st.tabs`)

Frozen in `REQUIRED_MAIN_SECTIONS`:

| Section | Must provide |
| --- | --- |
| Overview | Metrics, **Generic RCx DOCX download**, occupancy calendar → `occ_mode`, motor weekly, mech-cooling OAT bins, economizer weather summary, **BAS vs web OAT overlay** (±`oat_err`) + histogram, **Data inspection — raw CSV** (equipment dropdown → stacked Plotly lines for all numeric/status columns) |
| **Data Model** | Equipment → cookbook role → Haystack tag → CSV tree + feeds/fedBy + mapping status |
| Run Rules | Cookbook (+ custom); then review **FDD Plots** / **RCx** |
| Results by Category | Per **equipment type** then per device tables (not rule-family dropdown) |
| **FDD Plots** | Auto-run device rules; catalog-parity cards; **Sensor health — per sensor** matrix + chart (Word on Overview) |
| **RCx Plots** | Family → preset (Zones / AHU / Boiler / Chiller / Metering); zone comfort donut; one chart at a time; opt-in coverage |
| **Metering** | Electric/gas monthly + degree-day charts (category starter; expand later) |
| Export | CSV / session / health / data-model (Word template is Overview-only) |

Do **not** reintroduce `st.tabs` that evaluate every heavy pane (SIGSEGV risk on low-RAM hosts).

### FDD Plots + Generic RCx DOCX

- FDD Plots must render **N rule cards** for the applicable cookbook catalog for the selected device (not a sole one-rule selectbox as the only mode).
- Shared builder: `app.rule_card:build_rule_card` (params + mapping rows + coverage + **summary** + equation).
- Exactly one Word template: `assets/reports/Open-FDD_Generic_RCx_Report_v1.docx` via `load_generic_rcx_report` / Overview download.
- Do **not** resurrect per-equipment FDD DOCX, family RCx DOCX packs, or Export ZIP packs.

---

## Required chart APIs

Frozen in `REQUIRED_CHART_APIS` — must remain callable in `app/charts.py`:

- `rule_result_chart`, `multi_equipment_timeseries`, `multi_equipment_box`, `oat_scatter`
- `motor_weekly_runtime_chart`, `mech_cooling_oat_histogram`, `bas_vs_web_oat_histogram`, `bas_vs_web_oat_overlay`
- `equipment_inspection_chart`, `sensor_fault_chart`, `vav_comfort_donut`
- `max_plot_points`, `plotly_config`

Also keep `render_rcx_plots_tab`, `collect_oat_scatter`, `collect_role_series`, `rcx_preset_coverage`.

---

## Session persistence (zip uploads)

- Uploaded packages extract to a temp `vibe19_*` workdir. A pointer file `.last_browser_session.json` (see `app/browser_session.py`) records `workdir` / `building_root` so a **browser refresh** can reload via `load_package_from_dir` without re-upload.
- **Clear session** (sidebar) deletes the pointer and wipes the workdir — the only intentional wipe of loaded CSVs.
- Container / host restart still clears temp dirs (pointer becomes stale and is dropped).
- Env: `VIBE19_BROWSER_AUTOLOAD=0` disables restore (AppTest/CI); `VIBE19_BROWSER_SESSION_PATH` overrides the pointer path.
- Agent bootstrap (`.last_agent_session.json` / `VIBE19_BOOTSTRAP`) is separate and still preferred when present.

---

## Weather policy for reset scatters

- **HW / CHW / AHU SAT** scatters → web dry bulb (`wx_oa_t` / prefer-web OAT).
- **CW / cooling tower** scatter → web **wet-bulb** when available (Stull / psychrometrics), else dry bulb.
- Do not hard-link scatters to BAS OAT only; web weather is the default RCx reference.

---

## Required roles (mapping)

| Role | Used by |
| --- | --- |
| `hw_supply_t` | `hw_reset_scatter` |
| `chw_supply_t` | `chw_reset_scatter` |
| `cw_supply_t` | `cw_reset_scatter` |
| `duct_static` (+ `fan_status` / `fan_cmd`) | `duct_static_box` |
| `sat` | `ahu_sat_reset_scatter`, `ahu_dats` |
| `zone_t` | `zone_temps` |
| `mat` / `rat` / `oa_damper_pct` / `zone_flow` / `fan_cmd` | cohort overlays |

Empty coverage is OK when data is missing (`rcx_preset_coverage` + empty_reason). **Deleting the preset because one package has no CW points is not OK.**

---

## Plot rendering (stability)

- Downsample Plotly traces only (`VIBE19_MAX_PLOT_POINTS`, default ~5000) — never downsample rule math / exports.
- Lazy section navigation; package health graded summary (not warning floods).
- See `app/charts.py`, `app/data_contract.py`, `tests/test_charts.py`.

---

## Analytics golden baseline (perf guardrail)

Before changing analytics / RCx collectors / rule-batch caching, run:

```text
python -m pytest -q tests/test_analytics_golden.py
```

Committed CSVs under `tests/golden/analytics/` lock Overview analytics, RCx coverage/digests, and a compact rule-status digest for the deterministic fixture `tests/fixtures/analytics_pkg/`. Soft timings print with `-s`; absolute seconds only fail when `VIBE19_ASSERT_ANALYTICS_MAX_S` is set.

**After intentional numeric changes**, regenerate goldens:

```text
set VIBE19_UPDATE_ANALYTICS_GOLDEN=1
python -m pytest -q tests/test_analytics_golden.py -s
```

Optional BUILDING_100 fingerprint lane (when `VIBE19_TEST_PACKAGE_DIR` / local zip exists): same env writes `building100_fingerprints.json`.

Harness: `app/analytics_baseline.py`.

---

## Performance bottlenecks (findings)

Why the dashboard feels slow/clunky — **eager work on Streamlit reruns**, not “pandas can’t be fast.” Full write-up: [`PERF_BOTTLENECKS.md`](PERF_BOTTLENECKS.md).

**Worst offenders (historical / still watch):**

1. Export (and previously RCx) rebuilding catalog DOCX + full `rcx_preset_coverage` on every section visit
2. FDD Plots eagerly scanning RCx coverage for cards
3. Folder mode rematerializing all frames via `@st.cache_data` copy on every rerun
4. Rule batch: per-rule `merge_weather` copies + fat `plot_series` in session
5. `collect_oat_scatter` Python `iterrows`; multi-equip Plotly N×max_points traces

**Already required:** lazy radio (never eager `st.tabs` — SIGSEGV risk); RCx family → one preset; RCx Prepare DOCX + coverage opt-in; one Plotly on FDD Plots; downsample **traces only**.

**Before UI perf PRs:** green `tests/test_analytics_golden.py` (numeric lock). Prefer prepare-then-download for all DOCX/coverage downloads.

---

## Agent checklist before merge

- [ ] `REQUIRED_RCX_PRESET_IDS ⊆ {p.id for p in PRESETS}`
- [ ] `REQUIRED_MAIN_SECTIONS` / `REQUIRED_CHART_APIS` still match UI
- [ ] Plots cards + `build_rule_card` + Overview Generic RCx download still present ([`PLOTS_DOCX_VALIDATION.md`](PLOTS_DOCX_VALIDATION.md))
- [ ] `docs/RCX_PLOTS.md` + this file still match `PRESETS`
- [ ] `python -m pytest -q tests/test_rcx_presets.py tests/test_charts.py tests/test_rule_card.py tests/test_docx_report.py tests/test_analytics_golden.py tests/test_rule_param_sensitivity.py`
- [ ] param-sensitivity green (declared sliders change raw masks; no same-side tol cancel)
- [ ] Did **not** remove RCx Plots, FDD Plots, Metering, Export, or chart helpers (no duplicate Analytics tab — Overview owns motor/cool bins / BAS-vs-web hist)
- [ ] Did **not** reintroduce eager `st.tabs` / Export-on-visit DOCX+coverage rebuilds ([`PERF_BOTTLENECKS.md`](PERF_BOTTLENECKS.md))
- [ ] Append `SESSION_LOG.md` if presets / sections changed
