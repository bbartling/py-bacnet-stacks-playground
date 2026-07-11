# Dashboard contract (do not vibe-code away)

**Audience:** Cursor / Codex / any agent editing `vibe_code_apps_19`.

This Streamlit app is an **RCx + FDD review dashboard**, not a disposable demo. Features listed here are **product requirements**. Removing or silently renaming them without an explicit human decision + this doc update is a regression.

| Freeze source | Path |
| --- | --- |
| RCx preset ids | `app/rcx_plots.py` → `REQUIRED_RCX_PRESET_IDS` + `PRESETS` |
| UI sections + chart APIs | `app/dashboard_contract.py` |
| Tests | `tests/test_rcx_presets.py` |
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
| Overview | Metrics, occupancy calendar → `occ_mode`, motor weekly, mech-cooling OAT bins |
| Data & Mapping | Role / column mapping |
| **Data Model** | Equipment → cookbook role → Haystack tag → CSV column tree + DOCX |
| Run Rules | 50-rule cookbook (+ custom) |
| Results by Category | Status tables |
| **Plots** | Per-device **rule validation cards** (all applicable catalog rules); params + required/mapped points; lazy one-at-a-time Plotly via plot focus; one-click **Download FDD DOCX** |
| **RCx Plots** | Prebuilt presets above + generic role picker |
| Analytics | Motor hours, mech-cooling bins, sensor stats |
| Export | CSV / session / health / DOCX artifacts (incl. **Download equipment FDD DOCX**) |

Do **not** reintroduce `st.tabs` that evaluate every heavy pane (SIGSEGV risk on low-RAM hosts).

### Plots + DOCX validation cards

- Plots must render **N rule cards** for the applicable cookbook catalog for the selected device (not a sole one-rule selectbox as the only mode).
- Shared builder: `app.rule_card:build_rule_card` (params + mapping rows + coverage).
- Equipment DOCX (`build_equipment_fdd_docx`) must include **`[PLACE PLOT HERE`** stubs, tune params, and required vs mapped point tables — mirroring the cards.
- One-click download: **Download FDD DOCX** on Plots (and Export) — no Build-then-Download dance.

---

## Required chart APIs

Frozen in `REQUIRED_CHART_APIS` — must remain callable in `app/charts.py`:

- `rule_result_chart`, `multi_equipment_timeseries`, `multi_equipment_box`, `oat_scatter`
- `motor_weekly_runtime_chart`, `mech_cooling_oat_histogram`
- `max_plot_points`, `plotly_config`

Also keep `render_rcx_plots_tab`, `collect_oat_scatter`, `collect_role_series`, `rcx_preset_coverage`.

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

## Agent checklist before merge

- [ ] `REQUIRED_RCX_PRESET_IDS ⊆ {p.id for p in PRESETS}`
- [ ] `REQUIRED_MAIN_SECTIONS` / `REQUIRED_CHART_APIS` still match UI
- [ ] `docs/RCX_PLOTS.md` + this file still match `PRESETS`
- [ ] `python -m pytest -q tests/test_rcx_presets.py tests/test_charts.py`
- [ ] Did **not** remove RCx Plots, Plots, Analytics, Export, or chart helpers
- [ ] Append `SESSION_LOG.md` if presets / sections changed
