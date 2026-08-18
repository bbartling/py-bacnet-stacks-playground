# Vibe19 session log

Rolling changelog for **reference-example development** (e.g. BUILDING_100). This is a dev diary for testing the **template** — not requirements every fork must meet.

**Append newest entries at the top.** Keep entries short — link to code, not prose dumps.

For onboarding your own site, start with [`TEMPLATE.md`](TEMPLATE.md) and [`docs/CUSTOMIZE.md`](docs/CUSTOMIZE.md).

---

## 2026-08-18 — Per-session Streamlit isolation (Cloud / GHCR)

- Uploads extract to `{temp}/vibe19/{session_id}/` (`app/session_workspace.py`). Clear session wipes only that UUID dir.
- Cloud (`cfg.is_cloud`) never reads/writes `.last_browser_session.json`. Agent `.last_agent_session.json` skipped unless `VIBE19_BOOTSTRAP` is set.
- Tests: `tests/test_session_workspace.py`, `tests/test_cloud_session_isolation_apptest.py`.
- Docs: `docs/STREAMLIT_CLOUD.md`, `docs/DOCKER.md`, `docs/DASHBOARD_CONTRACT.md`.

---

## 2026-08-17 — Streamlit width=, UTC stamps, Haystack string `equip`

- Streamlit floor `>=1.51`; widgets use `width="stretch"` / `width="content"` (no `use_container_width`).
- `parse_utc_timestamp` accepts ISO-8601 `Z` and `+00:00` without pandas infer-format warnings.
- Sidecar maps: string `"equip": "AHU_1"` is a device id, not a nested package map.
- Agent docs: any-BAS package authoring in root `AGENTS.md`, Haystack guide, DATA_MODEL_DRIVEN, PACKAGE_SPEC.
- Tests: `test_parse_utc_timestamp_accepts_z_and_offset_without_pandas_warning`, `test_string_equip_is_device_id_not_package_map`.

---

## 2026-08-16 — Playground closeout (verify-only)

- No vibe19 code PR. Pin remains `open-fdd[reporting]==4.4.1`. Local `open_fdd.__version__` = `4.4.1`. `python -m pytest -q` → 625 passed, 15 deselected.
- `dump_tables` still runs for diagnostic **and** forensic `export_agent_bundle`; oracle CSVs (`vav_health_matrix.csv`, `mech_cooling_oat_bins.csv`, `motor_hours.csv`, `motor_weekly.csv`) stay in dumps/MANIFEST.
- GHCR `:latest` index digest `sha256:101126abbe4d0affe4ffac6a8cf03bd5a1f31fe8e7161e6eb354910f32760f07` (linux/amd64 + linux/arm64). Image revision **`4b710616`** (PR #92). Develop tip `#93` `1995b52f` did not change vibe19 — no rebuild.
- bensbench: `docker pull ghcr.io/bbartling/vibe19:latest` (do not docker build on the Linux bench).

---

## 2026-08-15 — PyPI OpenFDD 4.4.1 dump_tables + GHCR

- Pin `open-fdd[reporting]==4.4.1`. Diagnostic/forensic WattLab dump calls `open_fdd.analytics.dump_tables` so `vav_health_matrix.csv` (plus motor/mech CSVs) land in the Engineering Bundle and MANIFEST.
- Runtime floor stays `>=4.4.0,<5`. Do not reimplement VAV-health math in Vibe19.

---

## 2026-08-14 — PyPI OpenFDD 4.4.0 + VAV health matrix

- Pin `open-fdd[reporting]==4.4.0` (pyproject / requirements / constraints). Drop GitHub ZIP overlay in CI.
- Overview: canonical VAV health matrix after occupancy controls (`app/vav_health.py` adapter only).
- Runtime guard `>=4.4.0,<5`; catalog pin 62 diagnostics / hash `2e684dbb…`.
- GHCR `:latest` updates after this lands on develop (`vibe19-ghcr.yml`).

---

## 2026-08-14 — WattLab summary export: bool quantile crash

- `app/wattlab_dump.py`: coerce series to float64 (`_as_float_series`) before `quantile`/`diff` so boolean fault/flag columns do not raise `numpy boolean subtract`.
- Test: `tests/test_wattlab_dump.py::test_sensor_stats_tables_bool_flag_quantile`.
- Image tip `ghcr.io/bbartling/vibe19:latest` updates **after merge to develop** (PR smoke does not push GHCR). Then `scripts/docker_update_vibe19.ps1`.

---

## 2026-07-25 — BUG-030–040 notebook / xlsx agent fixes

- vibe20: in-place `prefill` (no wipe); ROI B=H + live NPV formula + `npv_usd_at_build`; preview `data_only=False`; validate warns empty E+; ECMs Advanced expander; tests `test_notebook_builder.py`.
- vibe19: Overview chart dedupe; relative day_zoom/Overview paths; inventory `n_priority_findings` (+ candidates covered).

---

## 2026-07-25 — Economizer free-cooling diagnostic plots + Eng Findings xlsx

- Overview: fan-on AHU/RTU delta scatter (MAT−RAT vs OAT−RAT), MAT residual, temps+damper overlay; |OAT−RAT|<10°F suppressed (G36).
- Eng Findings: same PNGs via `build_overview_charts` → DOCX §2 + Excel `Overview_Charts`.
- Analytics: `economizer_free_cooling_diagnostics`; charts in `app/charts.py`.
- Punchlist-first Excel: `app/reporting/xlsx.py` (`--xlsx` / UI download).

---

## 2026-07-25 — Eng Findings Excel notebook (punchlist-first)

- `--xlsx` / UI download: `app/reporting/xlsx.py` (Punchlist, Findings+day-zoom images, FAULT inventory, Overview charts, Suppressed_DQ, Quality_Gate).
- openpyxl in `engineering-report` extras + `requirements.txt`.
- Agents prefer `.xlsx`; DOCX remains available.

---

## 2026-07-25 — Eng Findings BUG-019–024 (VAV/FD agent packs)

- **BUG-019:** `--systems` / `--equipment-prefix` / `--rule-ids` / `--boost-terminal` scope ranking (`app/reporting/scope.py`).
- **BUG-020:** `--allow-priority N` / `--raise-max-findings` + UI checkbox; quality gate honors explicit raise.
- **BUG-021:** `--pin-finding` / `--drop-finding` / `--note` HITL (`app/reporting/hitl.py`).
- **BUG-022:** `day_zoom_error` JSON alias; gate fails on silent zoom skip after chart pass.
- **BUG-023:** FAULT inventory JSON (`*_fault_inventory.json`) with orphans + rollups.
- **BUG-024:** Run Rules panel agent/scope expander + session `batch_results` fallback.
- Tests: `tests/test_eng_findings_agent_knobs.py`.

---

## 2026-07-25 — Eng Findings BUG-016/017/018 + DOCX UX

- **BUG-016:** `attach_day_zoom_to_findings` records `skip_reason` (`no_result` / `no_fault_day` / `render_failed`) + `day_zoom_skip_reason`; DOCX muted note when zoom missing.
- **BUG-017:** Quality gate ignores anti-replace honesty (“Do not replace…”); still rejects proactive replace on weak classes.
- **BUG-018:** `format_analysis_period` from Overview dataset span; pipeline + Run Rules panel fill cover period.
- **DOCX UX:** Cover/section/table helpers aligned with vibe20 Energy Modeling client DOCX tokens (`_cover`, `_section_h1`, `_style_table_header`, muted `#4A5568`).
- Tests: `test_report_quality_gate`, `test_report_day_zoom`, `test_report_overview_export`, `test_report_docx`.
- Skill / validation: `skills/vibe19-engineering-report`, `docs/PLOTS_DOCX_VALIDATION.md`.

---

## 2026-07-23 — Engineering Findings Report (detection ≠ finding)

- **Second reporting product** beside static Generic RCx: `app/reporting/` (evidence packets, Passes 1–7 reviewer, ≤7 prioritized findings, quality gate, Kaleido charts, DOCX+JSON).
- Overview: **Generate Engineering Findings Report** button only (`render_engineering_findings_panel`); optional HITL include/note. Never rebuild on section visit.
- Headless: `python -m app.reporting.cli --checklist-json … --out-dir … --docx --json` (also accepts WattLab dump + `--run-rules`).
- Optional extras: `pip install '.[engineering-report]'` (`python-docx`, `kaleido`). Generic RCx path stays bytes-only / no python-docx.
- Tests: `tests/test_report_*.py`, `test_finding_*.py`, `test_false_positive_review.py`, `test_near_continuous_fault_review.py`, `test_peer_common_mode_detection.py`.
- Skill: [`skills/vibe19-engineering-report/SKILL.md`](skills/vibe19-engineering-report/SKILL.md). Docs: `PLOTS_DOCX_VALIDATION.md`, `DASHBOARD_CONTRACT.md`, root `AGENTS.md`.

---

## 2026-07-19 — Compressor runtime + WattLab dump v3 handoff

- **Compressor-only OAT bins:** CHW **pump status/cmd alone is not compressor proof**. Acceptable: compressor/chiller status, verified command, power/current. Chilled-water AHU valves excluded. Idle mapped compressors → `eligible_no_runtime`. Aggregates: `aggregate_device_hours` + `aggregate_active_hours` (one running device ⇒ equal). Design: `docs/superpowers/specs/2026-07-19-compressor-runtime-wattlab-release-design.md`.
- **WattLab `wattlab_dump_v3`:** default profile **`summary`** (shared `telemetry/`, no required `fdd_timeseries`); also `diagnostic` / `forensic`. Expanded sensor stats + `inferred_parameters` provenance; manifest stage/byte metrics.
- **Vibe 20 compatibility:** `load_bundle` accepts v2 + v3 additively; lazy telemetry path index. Docs: `docs/ANALYTICS.md`, root `AGENTS.md` / `README.md`.
- **GHCR:** publish **Vibe 19 only** via `.github/workflows/vibe19-ghcr.yml` (`:develop`, `:latest`, `:sha-…`); do **not** publish Vibe 20 for this change.

---

## 2026-07-19 — Mech-cooling status vs leave-temp proof + complete WattLab dump

- **Sidebar:** checkbox **Use mapped mechanical-cooling status proof** (default checked). *(Superseded for compressor proof: see entry above — pump alone is no longer OAT-bin proof.)* Unchecked → CHW leave temp via **CHW leave proof max °F** (`inferred: chw_leave_temp`); slider disabled while status proof is checked.
- **Overview coverage:** always lists every cooling-capable device (name, included/excluded, selected proof, runtime hours, reason). Never CHW valve %.
- **WattLab dump:** `_build_wattlab_dump_zip` always `run_rules` for the complete cookbook and refreshes `batch_results` (never reuse partial session results). Spec: `docs/ANALYTICS.md`.

---

## 2026-07-18 — Remove Energy Model tab; beef up WattLab dump for vibe20

- **Removed Energy Model tab/wizard:** deleted `app/energy_model.py`, `app/energy_wizard.py`, `configs/energy_defaults/`, and related contract entrypoints. Building characteristics are filled in vibe20; vibe19 Export is the sole handoff.
- **WattLab dump:** every FDD rule as `fdd_findings.csv` + `fdd_timeseries/<rule>__<equip>.csv` (auto-runs all rules if none run yet); analytic CSVs (topology, data_model, sensor health/fault, zone comfort, meters); `sensor_diurnal_24h.csv` (critical roles × hour × fan_state × weekday/weekend/holiday via `app/daytypes.py`); data-derived `model_seed.json`; `MANIFEST.json` for agent ingest.

---

## 2026-07-17 — RCx plant/duct-static presets + WattLab dump export

- **RCx presets:** `duct_static_ts` (duct static + `duct-static-pressure-sp` companion trace per AHU), `chw_temps_ts` and `cw_temps_ts` (supply + return + computed ΔT per chiller/plant/tower via new `collect_paired_temp_series`, pump-proof filter aware). `condenser-water-return-temp` added as a canonical role. Preset ids frozen in `REQUIRED_RCX_PRESET_IDS`; unique per-preset chart keys stop stale wet-bulb labels when switching presets.
- **WattLab dump (vibe20 handoff):** `export_agent_bundle` now writes `mech_cooling_oat_bins.csv` (+`ALL` total rows), `mech_cooling_coverage.csv`, `sensor_stats_{all,fan_on,fan_off}.csv` (every mapped role per equipment, sliced by fan/pump proof — `app/wattlab_dump.py`), `setpoints.csv` (occupied/unoccupied medians of `*-sp` roles), and `README_WATTLAB.md`. Alias-resolved raw columns (e.g. `fan_status`) fill role gaps with `source=column_alias`.
- **Export tab dial-back:** headline **Build WattLab dump (zip)** button (in-memory agent bundle → zip, no server bootstrap pointers); session restore kept; individual CSVs moved under an expander. Energy Model Package now embeds `model_seed.json` + optional `utility_bills.csv` (new bills editor).

---

## 2026-07-17 — Mech-cooling aggregation transparency + Compress-Archive zip fix

- **Mech cooling OAT bins:** `mech_cooling_oat_bins(include_total=True)` appends an `ALL` / "All mech cooling (total)" series summing hours across devices per bin (dark outlined bars in the chart + rows in the CSV). New `mech_cooling_coverage()` lists every chiller/DX candidate as included (with run proof) or excluded with a reason — e.g. BUILDING_100 CHILLER_1: "run roles mapped but never ON (all zero/flat)". Overview shows a coverage expander + CSV.
- **Zip upload ENOTDIR fix:** Windows `Compress-Archive` stores backslash paths; its `folder\` markers were extracted as files, then real files failed with `[Errno 20] Not a directory` on Linux/Docker. `_is_zip_dir()` in `app/package_io.py` (used by `_inspect_zip`, `extract_package_zip`, `expand_nested_zips`, `multi_zip`) treats them as directories; extraction `OSError` now surfaces as `PackageError` with a Compress-Archive rebuild hint. Regression tests in `tests/test_zip_backslash.py`; docs updated (PACKAGE_SPEC, BUILD_OPENFDD_PACKAGE, AGENTS).

---

## 2026-07-16 — GL36 AFDD internal-variable sliders

- FC1–FC15 equations now expose GL36 Table 5.16.14.5 sensor errors, ΔTSF, ΔTmin, ΔOSmax, ModeDelay, command/state boundaries, and AlarmDelay (`confirm_min`) in the left Rule tuning rail.
- Removed hardcoded `0.55°F` fan-heat use from equations; `delta_supply_fan` is independently tunable on every applicable FC rule. Separate εSAT/εRAT/εMAT/εOAT and coil-sensor tolerances replace the old one-size `mix_tol` while legacy overrides still propagate.
- Catalog-wide contract test catches `_f(p, key)` reads without a matching slider; fixed missing CHW pump-high sliders. Turnkey AppTest asserts representative GL36 sliders render without exceptions.

---

## 2026-07-16 — WattLab calibration hardening

- vibe20: weather suitability modes stamped on easy_button / calibrate reports; bill-month validation holdout (`--validation-months`); hour-shift lag-scan warning; `run_manifest.json` content hashes.
- vibe19 Energy Model: caption shows `weather_suitability` from vibe20 sidecar results.

## 2026-07-16 — Mapping staleness fix + in-app Energy Model wizard

- **FDD Plots mapping bug:** Data Model role edits now bump `mapping_rev`, clear stale `batch_results`, sync site/frame attrs; `rule_plot_series` prefers live remapped columns over baked `plot_series`. Damper + econ roles in editor defaults.
- **Energy Model self-contained:** `configs/energy_defaults/` + `app/energy_wizard.py` (resolve_profile, schedule prefill, ECM suggest, bin-hour quick savings, Energy Model Package zip). No vibe20 required for the form; EP sidecar optional.
- Turnkey AppTest asserts Building type selectbox renders without WattLab sibling.

---

## 2026-07-16 — ECON-7 + plot overlays (fan status / dewpoint)

- **ECON-7** *Economizer OK but not economizing*: web DP < 60°F and DB < 72°F (freeze-guard floor 35°F); cooling demand + damper below economizing threshold. Imperial sliders. Catalog **59** rules.
- FDD Plots: every rule card gets a 0/1 motor/fan status lane; temp plots that already show OAT also get `web-outside-air-dewpoint`.
- RCx timeseries: optional **Overlay motor / fan status (0/1)** checkbox → right-axis step traces.
- Pytest: `@pytest.mark.optional_zip` + `addopts = -m "not optional_zip"` so default suite is 0 skips (real BUILDING_100.zip lane opt-in).

---

## 2026-07-16 — Model Seed Bundle + overlap-window calibration

- `app/model_seed.py`: `infer_schedules`, `operating_signatures`, `build_model_seed_dict`
- `export_agent_bundle` writes `model_seed.json`, `schedule_inference.json`, `operating_signatures.csv`, `weather_observed.csv`
- `app/open_meteo.py` + Energy Model **Fetch Open-Meteo** / utility bills / **Calibrate against my data**
- vibe20: `weather_epw.py` (AMY EPW), `calibrate.py` + RunPeriod/hourly IDF patches → `calibration_scorecard.json`
- Turnkey UI: `tests/test_turnkey_app.py` (AppTest all sections + live HTML smoke)

---

## 2026-07-15 — Energy Model UI harden + brand scrub

- Hardened `app/energy_model.py` (session-keyed widgets, flat savings table, graceful WattLab missing, `width="stretch"`)
- Scrubbed leftover WattLab `.env` credentials; docs cover EnergyPlus-MCP sidecar + GHCR
- vibe19/vibe20 READMEs + `docs/DOCKER.md` Energy Model / `energyplus-mcp-dev` directions

---

## 2026-07-15 — Energy Model tab (WattLab easy button)

- Added **Energy Model** to `REQUIRED_MAIN_SECTIONS` + `app/energy_model.py` (responsive-defaults form, 3D massing, FDD suggest, subprocess → vibe20 `easy_button.py`)
- Env: `VIBE19_WATTLAB_DIR` (sibling `vibe_code_apps_20` auto-detected); Docker image `energyplus-mcp-dev` required for live sims
- Pair with vibe20: `wattlab_defaults.py`, `vibe19_bridge.py`, Good/Better/Best measure sets, chiller lockout + SAT reset patches

---

## 2026-07-15 — GHCR multi-arch agent contract

- Broke `:latest` when tags pointed at missing multi-arch blobs; fixed with QEMU amd64+arm64 no-cache rebuild
- Workflow: explicit QEMU platforms + `PUBLISH_PLATFORMS=linux/amd64,linux/arm64` + verify step + `workflow_dispatch` `no_cache`
- Agent model context: `vibe19_agent_spec/AGENTS.md` **rule 30**, `docs/DOCKER.md` **Publishing good containers**, streamlit-demo skill GHCR duty

---

## 2026-07-15 — Data inspection + browser session persistence

- Overview **Data inspection — raw CSV**: dropdown of all equipment (+ weather); stacked Plotly lines for every plottable column (largest chart on Overview)
- Uploaded zip survives browser **refresh** via `.last_browser_session.json` pointer + `load_package_from_dir`; **Clear session** deletes pointer + wipes temp dir (`VIBE19_BROWSER_AUTOLOAD=0` for AppTest)
- Spec: DASHBOARD_CONTRACT / AGENTS / streamlit-demo skill updated; `app/dashboard_contract.py` freezes new chart APIs + browser_session entrypoints
- Fix SV sidebar caption reading `equipment_frames` / `selected_equipment` (was dead `frames` key)

---

## 2026-07-14 — Sensor itemization, OAT overlay, pressure gates, RCx comfort pie

- **SV sweeps** stash per-role `sv_sweep_evidence` + confirmed masks; runner promotes to metrics (mirrors SV-RATE)
- **Sensor health** FDD panel: per-type matrix + per-sensor fault chart; sidebar per-type range/spike scales + role captions
- **OAT-METEO**: BAS vs web overlay (±`oat_err` band + fault lane); drop meaningless `%` — show mean/max °F deviation
- **RCx**: dry-bulb axis labels (tower keeps wet-bulb); VAV comfort donut with `n_below`/`n_above`
- **AHU-DUCTHI** conditional gate (fan OR duct static > `pressure_on_min`); **SCHED-247** pressure-on proof
- Fixed occupancy calendar Saturday key (`sat`, was mis-named `discharge-air-temp`); configs + goldens regenerated

---

## 2026-07-14 — Rule tuning inversions + dead FC4 + dt-aware confirm

- **Root cause (UI/plumbing, not FC2 math):** `confirm_min` default of 5.0 overrode every `confirm_seconds`; sidebar rewrote all params when any slider moved; startup delay raised `fault_pct` via smaller denominator
- **Phase 0 repro** (analytics_pkg AHU_1; BUILDING_100.zip not on host): `mix_tol` 1.15→3.0 cut fault hours 720→342; `confirm_min` inert when poll≫confirm (fixture poll ≈ 6h)
- Engine: per-rule confirm defaults synced; dt-aware `confirm_fault`/`hours_true`; FC4 uses DatetimeIndex; VLV-1 fan-only gate; coverage slider honors value (default 5%); expose FC8–15/TRIM/ECON-5 tols
- UI: store only changed params + direction hints + mixed-fingerprint warning; prefer fault hours next to %
- Tests: `test_confirm_and_duration.py`, catalog direction sweep; configs + goldens regenerated

---

## 2026-07-14 — Weather economizer rules + Generic RCx report

- **ECON-3** strict web DB/DP band (60–72°F, DP&lt;60°F) + integrated damper (default 90%); no BAS fallback
- New rules: **MECH-OAT-1**, **CHW-NOLOAD-1** (30 min confirm + load-satisfaction injection), **ECON-6**
- Overview analytics: `economizer_weather_summary` (opportunity / compliance / prohibited / winter hours)
- Reports: single `Open-FDD_Generic_RCx_Report_v1.docx` on Overview; removed multi-template pack
- Canonical catalog **58** rules; analytics goldens refreshed for economizer + rule digest

---

## 2026-07-13 — SV-RATE review fixes (widgets, units, perf)

- Dueling SV-RATE sidebar vs Run Rules widgets; metric °F/°C round-trip; role-mapped profile peek
- Dt-aware CO2 deadband; real-dt violation minutes; override_error evidence; SCHED-247 on-mask
- Vectorized operating-state windows; weather merge once per equipment; drop importlib.reload

---

## 2026-07-13 — SV-RATE + SCHED-247 + FDD/RCx plot companions

- **SV-RATE** (`SV-SLEW` alias): context-aware sensor rate-of-change (`sensor_rate.py` + profiles); Streamlit expander under Run Rules; `docs/SV_RATE.md`
- **SCHED-247**: always-on fan/pump runtime across AHU/plant equipment
- FDD plots: AHU temp charts companion OA damper + heat/cool valves (fan-cmd reserved for FC1/duct static); RCx presets for cooling/heating valves
- Canonical catalog **55** rules; analytics goldens refreshed

---

## 2026-07-13 — Haystack point names end-to-end + Data Model topology

- Rules / maps / DataFrames use Haystack slugs (`discharge-air-temp`, …) — one vocabulary
- Data Model: dedicated **Topology** (VAV fedBy / AHU feeds); point tables are points-only
- Docs: HAYSTACK_LIKE_MAPPING_GUIDE, COLUMN_MAP_JSON, DATA_MODEL_DRIVEN rewritten haystack-first

---

## 2026-07-13 — FC2 mix_tol dead-slider fix + param sensitivity

- FC2 algebra: `mat + tol < min(rat − tol, oat − tol)` (was same-side subtract → tol cancelled)
- FC5: `mix_tol` on both SAT and MAT sides
- New: `tests/test_rule_param_sensitivity.py` (FC2/3/5 + OAT-METEO + source cancel guard)
- Spec: AGENTS #26, pandas-fdd-rules checklist, OPENFDD_PARITY GL36 envelopes

---

## 2026-07-13 — README / GHCR pull-latest easy button (agent duty)

- Agents must keep **`README.md` Docker/GHCR** + **`docs/DOCKER.md`** documenting `:latest` tip + `scripts/docker_update_vibe19.(sh|ps1)` (pull + recreate)
- Spec rule #25 in [`AGENTS.md`](AGENTS.md); GHCR “Latest” on `sha-…` ≠ auto-update
- Image: `ghcr.io/bbartling/vibe19:latest` (tracks develop tip)

---

## 2026-07-12 — RCx fan/pump filter + PID AO data model

- RCx: checkbox filter to fan-on (air) / pump-on (plant); default on; instant Streamlit rerun
- PID-HUNT-1: sweep valve/damper/fan/pump 0–100% AOs (+ raw AO columns); not Loop-named points
- Regenerated BUILDING_100 / BUILDING_50 column maps via `scripts/gen_building_openfdd_maps.py`

---

## 2026-07-12 — GHCR multi-arch (amd64 + arm64)

- `vibe19-ghcr.yml`: QEMU + Buildx → `linux/amd64,linux/arm64` (Pi 4/5 64-bit)
- Doc: [`docs/DOCKER.md`](../docs/DOCKER.md)

---

## 2026-07-12 — Perf bottleneck findings documented

- [`docs/PERF_BOTTLENECKS.md`](docs/PERF_BOTTLENECKS.md) — ranked UI/data bottlenecks (eager Export/FDD coverage, Folder cache copies, rule-batch copies, iterrows scatters)
- Linked from AGENTS + DASHBOARD_CONTRACT; RCx family/lazy DOCX already mitigates worst RCx path

---

## 2026-07-12 — Analytics golden baseline (perf guardrail)

- `app/analytics_baseline.py` — canonicalize + fingerprint Overview/RCx/metering + compact rule digest
- Fixture `tests/fixtures/analytics_pkg/`; goldens `tests/golden/analytics/`
- `tests/test_analytics_golden.py`; regen with `VIBE19_UPDATE_ANALYTICS_GOLDEN=1`
- Doc: [`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md) analytics golden section

---

## 2026-07-12 — FDD Plots rename + RCx family / lazy DOCX

- Main section **Plots** → **FDD Plots** (`REQUIRED_MAIN_SECTIONS`)
- RCx: mechanical family → preset (AHU no longer lists plant/meter); Prepare DOCX + coverage opt-in
- Specs/skills: DASHBOARD_CONTRACT, RCX_PLOTS, PLOTS_DOCX_VALIDATION, streamlit-demo / plotly skills

---

## 2026-07-12 — RCx metering (electric / gas)

- Presets `meter_elec_cdd` / `meter_gas_hdd`: monthly energy from kW or gas rate + stats + scatter vs CDD/HDD (65°F)
- `app/metering.py`; roles `elec_power_kw`, `gas_flow` (+ aliases)

---

## 2026-07-12 — Catalog-parity Plots cards + RCx catalog DOCX

- `app/rule_plot_meta.py` — shared catalog fields / plot series / analytics hints
- Plots expanders mirror RULE_PLOT_CATALOG (facts, Haystack, series, full sliders, fit lines)
- FDD DOCX mirrors enriched cards; **Download RCx catalog DOCX** on RCx + Export
- MD generator refactored to import meta (no drift)

---

## 2026-07-12 — Drop Analytics; beef RCx Plots

- Removed **Analytics** tab (duplicate of Overview motors / cool bins)
- RCx: named Plot dropdown (chart type in label); `zone_comfort_rank` from Overview schedule + zone band
- AHU/HW/CHW scatters vs web dry-bulb; CW scatter vs wet-bulb with dry-bulb × ref
- Fan-mode summary tabs retained for AHU/VAV

---

## 2026-07-12 — Dataset UX + required per-CSV Haystack sidecars

- Removed Overview workflow table; zone defaults **70 / 75 °F**
- Merged Data & Mapping into **Data Model** (mapping status at bottom); dropped Data & Mapping section
- Package requires sibling Haystack JSON per equipment CSV (`history_wide.json` | `*.column_map.json` | `column_map.json`); weather optional; nested zips expanded
- `app/sidecar_maps.py` + PACKAGE_SPEC update

---

## 2026-07-12 — Rule plot catalog (all 50)

- Added `docs/RULE_PLOT_CATALOG.md` — per mechanical family: Haystack tags, plot series, sliders, analytics hints
- Generator: `scripts/generate_rule_plot_catalog.py`
- Extended `COOKBOOK_TO_HAYSTACK_POINT` for plant/economizer/weather roles used by the catalog

---

## 2026-07-11 — Plots + DOCX validation UX overhaul

- `app/rule_card.py`: shared card builder (params, required/mapped roles, coverage %)
- Plots: all applicable rule cards + filters + plot focus (lazy Plotly) + one-click **Download FDD DOCX**
- DOCX mirrors cards with **PLACE PLOT HERE**, params, mapping tables
- Freeze: `build_rule_card` entrypoint; DASHBOARD_CONTRACT Plots/DOCX section
- **Spec sync:** `docs/PLOTS_DOCX_VALIDATION.md`; plotly + streamlit-demo skills; `AGENTS.md` rule 21; BUILD_CHECKPOINTS / TEMPLATE

---

## 2026-07-11 — Bench VLV-1/SCHED-1/chiller + DOCX data-model

- VLV-1: closed valve + (SAT vs SP **or** SAT vs MAT); fan gate
- SCHED-1: optional zone comfort band; Overview zone sync → SCHED-1 params
- Chiller weekly: pump preferred, else chiller/compressor/enable status (never leave-temp)
- Plots caption for economizer / FC6 data gaps
- **Data Model** section + DOCX reports (`python-docx`): equipment FDD, data-model tree, analytics
- Freeze: `REQUIRED_MAIN_SECTIONS` includes Data Model; DOCX entrypoints in `dashboard_contract`

---

## 2026-07-11 — Dashboard contract (full catalog freeze)

- Validated: HW/CHW leave vs web OAT, CW/tower vs wet-bulb, duct-static box
- **Added** `ahu_sat_reset_scatter` (AHU SAT vs web OAT)
- Freeze **all 12** current RCx presets in `REQUIRED_RCX_PRESET_IDS`
- `app/dashboard_contract.py` freezes main UI sections + chart APIs; Streamlit imports `REQUIRED_MAIN_SECTIONS`
- Spec: `docs/DASHBOARD_CONTRACT.md` · tests: `tests/test_rcx_presets.py`

---

## 2026-07-11 — Multi-zip upload + agent prerun (no GHCR push)

- Sidebar accepts **multiple** package zips; `app/multi_zip.py` merges parts under agent 2 GB cap
- **Map + prerun all faults** after load (`app/agent_prerun.py`)
- Spec: `vibe19_agent_spec/docs/AGENT_CSV_PREPROCESS.md`

---

## 2026-07-11 — GHCR caps crash + data-contract warnings

- Fix Zip branch `NameError: caps` → use `agent_caps` for dataset size captions
- `app/data_contract.py`: quality trusted-window / columns.csv intersect / VAV topology warnings (no invented trust)
- Docker bootstrap docs: container-visible `/data` paths, host port vs :8501 (`docs/DOCKER.md`)
- AppTest bootstrap regression; GHCR republish on push

---

## 2026-07-11 — Streamlit 500 MB upload + GHCR

- `.streamlit/config.toml` → `server.maxUploadSize = 500` (fixes browser “200MB per file”)
- GHCR workflow `.github/workflows/vibe19-ghcr.yml` → `ghcr.io/<owner>/vibe19`
- Docs: DOCKER / STREAMLIT_CLOUD / AGENTS / PACKAGE_SPEC note both upload + package caps

## 2026-07-11 — Data-model-driven typed equip (WP1–4)

- `resolve_equipment_type` / `stamp_equipment_type` — attrs → role_map/column_map `equipType` → id fallback; HP/RTU normalize
- Motors: mapped fan/pump roles before named-pump regex; omit inventing supply fan from raw columns when roles empty
- RCx: typed membership only (no id-substring) in `collect_oat_scatter` / `collect_role_series`
- Mapping selectbox indexes current type; session_config round-trips `equipment_type` (+ optional `chw_pump_equipment`)
- Docs: `DATA_MODEL_DRIVEN.md`, AGENTS, Haystack guide, DOCKER (500 MB default explicit)
- Package default remains **500 MB** zip+expanded (`DEFAULT_PACKAGE_MB`); Dockerfile does not lower caps

## 2026-07-11 — Overview/sidebar UX + valve ban

- Units radio drives CHW leave + zone comfort sliders (°F/°C display; stored °F) via `_temp_threshold_slider`
- Removed **Filter rules** text input; category selectbox remains
- Occupancy calendar → `occ_mode` **always on** (no Apply-calendar checkbox); AGENTS hard rule
- Removed **AHU CHW valve = mech cooling** checkbox; `include_ahu_chw_valve` deprecated/always False
- Docs: `AGENTS.md`, `vibe19_agent_spec/AGENTS.md`, `PACKAGE_SPEC`, `DATA_MODEL_DRIVEN`, `ROLE_MAPPING_PARITY`, Haystack guide, CUSTOMIZE

## 2026-07-11 — Docker zip-only + hero reorder

- Dockerfile: `APP_MODE=cloud` + `VIBE19_DOCKER=1` (hide Folder / dead server paths by default)
- `app/config.py`: Docker without mounted `data_root` stays zip-only even if `APP_MODE=local`
- Streamlit: validate/clear missing folder bootstrap paths; fall back to Zip; hero = title → subtitle → smaller logo → how-it-works
- Docs: `docs/DOCKER.md`, `docs/CUSTOMIZE.md` — Folder needs volume + `APP_MODE=local`

## 2026-07-11 — 500 MB package default + size UI + CUSTOMIZE.md

- Package caps: **500 MB** zip + expanded for local/auto/cloud (`DEFAULT_PACKAGE_MB`); env overrides unchanged
- Report + UI: `zip_mb` / `uncompressed_mb` in package report; sidebar + Overview show size vs limits (`dataset_size_caption`)
- Agent fork guide: `vibe19_agent_spec/docs/CUSTOMIZE.md` (DB loader pattern, branding, CUSTOM-*, Docker vs Cloud); TEMPLATE / AGENTS / root AGENTS synced

## 2026-07-11 — Session restore UX + Docker self-host

- Sidebar + Export: **Download / Upload** `session_config.json` (`openfdd_session_v1`) and distinct `fault_settings.json` — Cloud-safe round-trip (zip → tune → download → later zip + upload)
- Helpers: `_session_config_payload` / `_apply_session_config_bytes` / `_render_session_config_io` in `streamlit_app.py`
- Docs: `docs/STREAMLIT_CLOUD.md` round-trip; `docs/DOCKER.md` + `Dockerfile` (Community Cloud does **not** use Dockerfile)
- Custom rules polish still in tree (`custom_*`, CUSTOM_RULES.md)

## 2026-07-11 — Custom pandas rule boilerplate

- Agent workspace: `app/rules/custom_boilerplate.py` (templates + `EXAMPLE_SAT_HIGH` / `EXAMPLE_ZSCORE`), `custom_rules.py` (`CUSTOM_RULES`), `custom_registry.py` (canonical 50 + `CUSTOM-*`)
- Spec: `docs/CUSTOM_RULES.md`; skill + AGENTS point at custom paths; Overview shows `50 (+N custom)` when extras present
- Env `VIBE19_INCLUDE_EXAMPLE_CUSTOM_RULES=1` loads examples without editing `custom_rules.py`

---

## 2026-07-10 — Agent → Streamlit bootstrap handoff

- `app/bootstrap.py` + `.last_agent_session.json` / `VIBE19_BOOTSTRAP`
- `agent_afdd.py` writes bootstrap after export; Streamlit auto-loads package + params (+ optional auto-run rules)
- Confirm delay default 5 min (0–60); chiller run-hours pump-only (no leave-temp); weekly avg OAT + occ schedule UI

---

## 2026-07-10 — Weekly OAT + schedule UI + DX-only cooling bins

- Weekly motor charts: avg OAT °F while on (secondary axis); air-side bare-min occupied hours line from calendar
- Overview: occupancy **time pickers** + zone comfort low/high → VAV-1 params / SCHED-1
- Mech-cooling OAT bins: pump/DX first, leave-temp backup only; **never** CHW valves; bins sorted cold→hot *(historical — superseded 2026-07-19: pump alone is not compressor proof; see top entry)*
- `scripts/smoke_streamlit_app.py` for AppTest / import smoke
- AGENTS.md HVAC context for Codex (pump-first, no valve bins) *(historical — motor pump ≠ OAT compressor proof)*

---

## 2026-07-10 — Agent API + weather policy + AFDD turnkey

- `app/agent_api.py` + `scripts/agent_afdd.py` — load zip/folder, run 50 rules / analytics / RCx, export bundle (no HTTP)
- `app/weather_resolver.py` — `oa_t_effective` (web primary, BAS fallback); OAT-METEO both-required
- Package `column_map.json` on `PackageLoadResult`; role_map gap + RCx coverage + tuning assistant reports
- Streamlit: fault_settings / session_config path+upload I/O; RCx diagnostics expander; gap report on Mapping/Export
- Windows tests: `scripts/run_tests_local.ps1`
- Tests: weather, agent API/CLI smoke, column_map, RCx coverage, gap, fault settings

---

## 2026-07-10 — RCx Plots + web weather + units + occupancy (spec sync)

- **RCx Plots** tab: prebuilt multi-equip overlays, duct-static box (fan-on), HW/CHW/CW scatters, generic picker, outlier highlight — `app/rcx_plots.py`, `app/ui_rcx_tab.py`, `app/charts.py`
- Web OAT default for analytics/free-cool; dewpoint (Magnus) + wet-bulb (Stull) — `app/weather_psychrometrics.py`
- Sidebar: imperial/metric display, prefer web OAT, CHW leave proof °F, weekly occupancy calendar — `app/occupancy.py`, `app/unit_system.py`
- Rules: ECON-3 web free-cool + SAT≈SP; VAV-7 fixed/high flow; **CW-OPT-1** replaces WX-2
- `scripts/csv_parity_check.py` for any building folder
- Spec: `docs/RCX_PLOTS.md`; skills + AGENTS + BUILD_CHECKPOINTS updated

---

## 2026-07-10 — Dead-code cleanup

- Removed leftover local dirs `haystack_rdf/`, `fdd_dashboard_model/`, `fdd_app/` (killed stale uvicorn:5000 lock)
- Deleted retired skills (RDF / Flask / deploy / point-catalog) and obsolete Rust/FastAPI agent docs
- Removed unused `shared/occupancy.py`; scrubbed `fdd_app`/`haystack_rdf` refs from skills, TEMPLATE, DATA_CONTRACT, OPENFDD_PARITY, ROLE_MAPPING
- Dropped obsolete BRANCH_RECONCILIATION doc test; `shared/env_loader.py` no longer probes `fdd_app/.env`
- gitignore blocks recreating stale packages
- Spec trimmed to Streamlit-only map

---

## 2026-07-10 — Mech cooling OAT bins + rainbow multi-axis plots

- Restored **mechanical cooling vs OAT (5°F bins)** for chillers + AHU DX compressors only (not cool-valve AHUs)
- Overview/Analytics: **per-motor** run-hours table; histogram + CSV export
- Plots: single figure, unique y-axis domains per unit family, rainbow palette, fault swim-lane shade
- Fixed cookbook equation mojibake (`≥`, `°F`, `ΔT`, …)

---

## 2026-07-10 — Operational gates + SKIPPED_EQUIPMENT_OFF

- Registry `RULE_GATES` (ALWAYS / RUN / CONDITIONAL) in `app/rules/operational_gate.py`
- Prefer `fan_status` / proof over `fan_cmd`; hydronic & compressor gates for plant/HP
- New status `SKIPPED_EQUIPMENT_OFF` when proven-off entire window
- Sidebar: **Require operational proof** (default on) + per-rule gate/startup sliders
- Plots: sensor fault summary stats CSV; PID-HUNT-1 replaced SV-4 earlier
- Spec: `docs/OPERATIONAL_GATES.md`

---

## 2026-07-10 — Sidebar sliders restored + per-device Plots

- Left rail again: Rule tuning sliders + category filter + **Rerun cat.**
- Plots: device type → device → applicable fault-category charts (no Rule Inventory tab)
- Export kept; AppTest clean

---

## 2026-07-10 — Plots tab + run-by-category + slim sidebar

- Sidebar: Browse + folder path only (removed Site ID, notes, rule-tuning rail, browser upload)
- **Run Rules**: all 50 or one mechanical category; optional tuning expander
- **Plots** tab: unit-separated panels + confirmed-fault bool row; Plotly camera PNG/JPEG download
- Column map JSON includes `units`; charts never mix °F with % / cfm
- Export: CSV + Haystack JSON only (no engineer-note reports)

---

- Column map JSON prefers Project Haystack–style `siteRef` / `equip` / `device` / `equipType` / `points` (`discharge-air-temp` → cookbook `sat`)
- Legacy `equipment` / `column_roles` still loads; rules unchanged (cookbook roles)
- Sidebar: Browse folder… + any building path (not locked to BUILDING_100); removed multi data-input modes
- LLM prompt + agent spec (`AGENTS.md`, streamlit-demo skill, HAYSTACK guide) updated
- Brand: Open FDD Vibe Coder

---

## 2026-07-10 — Category tabs + JSON column map (BUILDING_100)

- Reorganized Streamlit tabs: Overview / Data & Mapping / Run / Results by Category / Inventory / Trends / Export
- Results + inventory grouped by mechanical family (sensor→ahu→vav→plant→…) with natural rule-id sort
- Added `app/column_map_json.py` + `configs/building_100_column_map.json` + LLM prompt in README
- BUILDING_100: 48 equipment, 50 rules → PASS 121 / FAULT 215 / SKIPPED 187 / N/A 1877 / ERROR 0
- Tests: 135 passed

---

- Added `skills/vibe19-streamlit-demo/SKILL.md`; retired FastAPI/Flask/Haystack/deploy skills to redirects
- Rewrote `vibe19_agent_spec/AGENTS.md` for Streamlit-only demo
- Sidebar default: **Upload CSV files** (`st.file_uploader` multi-select); path modes optional
- Installed official Streamlit agent skills globally (`streamlit skills -y` — Windows symlink fallback)
- Tests: 129 passed

---

## 2026-07-09 — Bulk confirm-streak fix: BUILDING_100 full parity @ 0.5h

Applied LAG-based transition streak CTE to all remaining SQL rules (FC1–FC13, VAV-1,
ECON-2, etc.). Fixed ECON-2 `confirm_seconds` registry mismatch (900 → 300 to match
cookbook). **368 pass / 0 fail / 11 skipped** — material mismatch list empty @ 0.5h.
FC7/ECON-5 remain valid skips (missing historian roles).

---

**Root cause found via `debug_rule_parity.py` + a pandas replay of both streak
algorithms on the dumped raw-fault series:** the shared `grp`/`ranked` confirm CTE
pattern (`SUM(CASE WHEN raw_fault = 0 THEN 1 ELSE 0 END) OVER (... ROWS UNBOUNDED
PRECEDING)` as the streak id) puts the boundary `raw_fault = 0` row into the *same*
partition as the following True-run, so `ROW_NUMBER()` counts that boundary row as
position 1. Every True-run therefore reaches `{{CONFIRM_ROWS}}` one row earlier than
pandas `confirm_fault()` (which groups on `raw != raw.shift()`), over-confirming by
~1 row per qualifying fault streak — this is what produced the 22.4h (AHU_1) / 32.7h
(AHU_2) OAT-METEO deltas (Stage 4a's LEFT JOIN fix did not touch this).

**Fix (`sql_rules/oat_meteo_fault.sql`):** replaced the streak id with a `LAG`-based
value-transition id (`lagged` CTE + `raw_fault IS DISTINCT FROM prev_raw_fault`),
matching pandas semantics exactly. Also dropped the population-level
`WHERE h.oa_t IS NOT NULL` filter so `COUNT(*)` denominator is the full AHU timeline
(matches Python `len(d)`), moving the null check into the per-row `CASE` instead.

**Verified:** re-ran `run-rules` + `compare` (tolerance 0.5h) — OAT-METEO now
0.000h delta on both AHU_1 (285.417h/10.85%) and AHU_2 (1086.583h/41.29%), exact
match to the pandas oracle. `ECON-4` was fixed concurrently (same `LAG`-based
streak-transition pattern) in a parallel pass on this branch; regenerating the
full SQL rule batch + oracle compare picks up both: **314→320 pass, 54→48 fail**
@ 0.5h. Also fixed two pre-existing bugs in `debug_rule_parity.py`
(`CookbookParam.name`→`.key`, `CookbookRule.fn`→`.compute`) that blocked running it.

**Still material (unrelated to OAT-METEO, same shared CTE bug likely present):**
FC8, FC9, FC10, FC12, FC13-SAT-HIGH, FC2, ECON-2, VAV-1 — candidates for the same
`LAG`-based streak fix in a follow-up pass (out of scope here; minimal diff to
OAT-METEO only per this task).

**Docs:** `STAGE4_PARITY_REMAINING_PLAN.md`, `MERGE_STATUS_REPORT.md`,
`benchmarks/RUST_DATAFUSION_PARITY_BENCHMARK.md` (regenerated).

---

## 2026-07-09 — Branch reconciliation + Stage 4 working branch

**Audit:** Only `develop` exists (local + remote). Default branch verified: **develop**. Stale `master` and `stage3-datafusion-parity-building100` already deleted after fast-forward merge. No stranded commits.

**Baseline rerun @ 0.5:** 314 pass / 54 fail / 11 skipped; 19/19 SQL rules; max Δ 32.7h OAT-METEO. Unchanged from Stage 4a.

**Working branch:** `stage4-finish-parity-and-tuning` from `develop` @ `b93a929`.

**Docs:** `BRANCH_RECONCILIATION_STAGE4.md`

**Next:** Stage 4 Priority A — OAT-METEO timestamp/join audit.

---

## 2026-07-09 — Stage 3: VAV_7 zone_t fix + SQL tunable parameters

**Done:**
- **VAV_7 zone_t regression fixed** — Python `_resolve_zone_t()` ranks candidates (prefer `vav_*_space_temp_f`, reject alarm/limit/_58/_59). Rust `role_rank.rs` + ingest `pick_best_column`; skip limit columns in `columns.rs`.
- **SQL rule tuning plumbing** — `registry.yaml` `parameters:` (VAV-1, FC13, OAT-METEO, zone rollups); `rule_tuning/defaults.yaml`; Rust `tuning.rs` merge/clamp/placeholder guard; runner injects tuned params + recomputes `CONFIRM_ROWS`.
- **Python API** — `GET /api/sql-rules`, `POST /api/sql-rules/preview`, `POST /api/sql-rules/save-profile` (`sql_rules_registry.py`).
- **Static frontend** — `dashboard_sql_tuning.js` panel (parity badge, sliders, preview/save); wired in `generate_dashboard.py`.

**BUILDING_100 @ 0.5 (2026-07-09 14:58 UTC):** **314 pass / 54 fail** / 11 skipped. Was **228/52** @ `bdb8881`. **19/19 SQL rules succeed.**

**Proven:** FAN-RUNTIME-HOURS, FAULT-ELAPSED-HOURS, AVG-ZONE-TEMP, ZONE-COMFORT-PCT, FC1, FC3, FC11, ECON-1.

**Material mismatch (residual):** OAT-METEO, FC8, FC10, FC2, FC9, FC12, FC13, ECON-2, ECON-4, VAV-1 (small per-VAV confirm deltas).

**Timings:** oracle export ~147s; Rust ingest ~3.2s (+ weather 31,577 rows); run-rules ~197s; compare ~1.4s.

**Tests:** 103 pytest passed, 1 skipped; Rust workspace tests + clippy clean.

**Next:** OAT-METEO timezone join audit; FC13/FC8/FC10 threshold exactness; complete `parameters:` for remaining FC rules; per-request SQL preview via Rust CLI.

---

## 2026-07-09 — Stage 2 parity push (confirm CTE, ingest column priority, compare report)

**Done:**
- **Confirm/streak SQL** — FC2–FC12 + FC13 use `{{CONFIRM_ROWS}}` (600s cookbook default); `COALESCE(oa_damper_pct,0)` matches Python `fillna(0)`.
- **Fan gate** — FC2/FC3/FC7 use `fan_cmd` only (no `fan_status` fallback when `fan_cmd` column exists).
- **Ingest column priority** — `dat_reset_f→sat_sp`, `discharge_air_temp_f→sat` (fixes SQL=0 FC13); `pick_best_column` in `fdd_store`.
- **`fdd_cli compare`** — PR-reviewable markdown: per-rule/equipment summaries, top-20 abs/pct mismatches, proven/near/material sections.
- **`debug_rule_parity.py`** — sample-level Python oracle debug → `.cache/debug/`.
- **Weather staging** — already wired in `warmup_cache()` before Rust ingest.

**BUILDING_100 @ 0.5 (2026-07-09 13:48 UTC):** **228 pass / 52 fail** / 11 skipped. Was 234/46 before ingest SAT fix exposed VAV_7 `zone_t` alarm-column regression.

**Rule highlights:** FC2 AHU_1 outlier **fixed** (was Δ1147h). FC13 **near parity** (AHU_1 Δ11.3h, AHU_2 Δ21h). FC9/FC12/FC2 AHU_2 **near parity** (≤18h). FC1/FC3/FC11/ECON-1 **proven**. **VAV_7** zone analytics broken (alarm limit column picked as `zone_t`) — next fix.

**Tests:** 103 pytest passed, 1 skipped; Rust 15 tests, clippy clean.

---

**Done:**
- **`fdd_app/export_pandas_oracle.py`** — cookbook-engine oracle → `.cache/oracle/pandas_rules.json` (207 records BUILDING_100).
- **`fdd_cli compare`** — per rule/equipment/metric, tolerance, markdown report, skip missing roles.
- **Poll interval** — `{{POLL_SECONDS}}` substitution + ingest sidecar manifest.
- **19 SQL rules** — original 8 + FC1–3, FC7–12, ECON-1/4; registry metadata (pandas fn, parity status, blockers).
- **Role mapping** — `columns.rs` aligned with Python; `ROLE_MAPPING_PARITY.md`.
- **Dashboard** — `VIBE19_RUST_CACHE=1` optional Parquet warmup via `rust_fdd_bridge.warmup_cache()`.
- **Bugfix** — Utf8View `equipment_id` serialization for compare keys.

**BUILDING_100 parity:** 229 pass / 49 fail @ 0.5 tolerance. Analytics rules (fan runtime, zone temp, comfort pct) **proven**. VAV-1 partial (confirm window). OAT-METEO/ECON-2/FC13 **proxy gaps documented**. FC1 blocked (`duct_static_sp`).

**Tests:** 103 pytest passed; `cargo test` 12 passed; clippy clean.

---

## 2026-07-09 — Rust FDD core stage 1 (Arrow + Parquet + DataFusion)

**Done:**
- **`rust_fdd_core/`** — 7 crates: `fdd_core`, `fdd_csv`, `fdd_store`, `fdd_sql`, `fdd_rules`, `fdd_bench`, `fdd_cli`. Validates CSV tree, ingests to Parquet (`.cache/parquet/`), runs DataFusion SQL.
- **`sql_rules/`** — 8 deterministic rules + `registry.yaml` (fan runtime, zone comfort, OAT/SAT/ECON faults, rollups).
- **Column role mapping** — `columns.csv` → logical names for SQL (`fan_cmd`, `zone_t`, `oa_t`).
- **Docs** — `RUST_CORE_STAGE1.md`, `PYTHON_REDUCTION_PLAN.md`, `PANDAS_TO_SQL_RULE_MIGRATION.md`, `RUST_DATA_MODELING_OXIGRAPH_EVAL.md`, benchmark report.
- **Tests** — `cargo test` 7 passed, `clippy -D warnings` clean; **102 pytest passed**, 1 skipped (unchanged dashboard).

**Not done (next PR):** pandas↔SQL numeric `fdd_cli compare` per rule; 42/50 cookbook rules still pandas-only.

**Follow-up (same PR pass):** Fixed `columns.csv` parsing (`col` + `point_role` headers), BUILDING_100 ingest (1.5M rows / 3.2s), **8/8 SQL rules pass** on real data. Added `rust_fdd_bridge.py` + `/api/sidecar/status` rust_fdd block.

---

## 2026-07-09 — Package rename: `csv_fdd_dashboard` → `fdd_app`

**Done:**
- **Split layout** — `fdd_app/backend/` (FastAPI + pandas FDD), `fdd_app/frontend/static/` (JS/CSS), `fdd_app/sidecar/` (open-fdd bridge), `fdd_app/tests/`.
- **Removed dead code** — `wsgi.py`, `dashboard_server.py`, `pandas_rule_scaffolds_for_missing_vav_points.py`.
- **Deleted generated artifacts** — all `*.html`, `plotly.min.js`, generated CSVs, log files (gitignored; regenerate via `backend/generate_dashboard.py`).
- **Updated** Dockerfiles, `feather_cache`, `env_loader`, `AGENTS.md`, skills/docs. **102 pytest green.**

---

## 2026-07-08 — FDD performance stack + open-fdd sidecar (hybrid)

**Done:**
- **Disk fault cache** — `fault_disk_cache.py` persists cookbook results under `.cache/faults/{data_token}/`; server restart is now a cache hit, not a full recompute. Integrated into `cookbook_engine.equipment_view` / `equipment_series` / `run_page`; invalidated by `_data_token()` + `_RULE_SET_VERSION`. (Fixed Windows path: `|` → `_` in cache keys.)
- **Motor runtime batch** — `motor_runtime_cache.compute_all_motor_stats(raw)` reuses already-loaded raw frames instead of per-motor `load_history_wide()` loop (~180s → seconds); disk-cached by `data_token`. Wired into `generate_dashboard.compute_context` `motor_runtime` branch.
- **DuckDB rollups** — `duckdb_rollups.py`: zone comfort %, OAT bins, chiller OAT-bin hours, weekly means over Feather/Parquet; pandas fallback when DuckDB absent. `compute_mech_cool_oat_bins` uses it.
- **Parquet sidecars** — `haystack_rdf/feather_cache.read_history_parquet()` with column pruning, same mtime invalidation as Feather.
- **open-fdd sidecar (optional)** — `historian_export.py` (logical frames → `telemetry_pivot.jsonl` + `.arrow`, role map `zone_t→zn_t` etc.), `cookbook_sidecar.py` (HTTP `/api/fdd/run`, `is_available()` health, **pandas fallback**), `cookbook_rules_sql.yaml` + `cookbook_sql.py` (dual-backend SQL for SV-RANGE/SV-FLATLINE/VAV-1/OAT-METEO/MOTOR-EXCESS; annotates pandas results with `sidecar` block when `OPENFDD_USE_SIDECAR=1`).
- **Rule consolidation** — `cookbook_kpi.py` sources overview KPIs from the cookbook engine; index page shows cookbook SCHED-1 hours alongside legacy excess-fan KPI. Deprecation banners on `pandas_rule_scaffolds_for_missing_vav_points.py`, `sensor_qa_engine.py`, `economizer_fdd_engine.py`.
- **API** — `GET/POST /api/historian/export`, `GET /api/sidecar/status`; optional export on warmup via `OPENFDD_AUTO_EXPORT=1`.
- **Deploy** — `fdd_app/docker-compose.sidecar.yml` (vibe19-api + openfdd-edge, shared historian volume); `DEPLOY.md` env vars + sidecar quick start.
- **Tests** — `test_fault_disk_cache.py`, `test_cookbook_sql.py`, `test_historian_export.py`, `test_duckdb_rollups.py`, `test_cookbook_sidecar_parity.py` (skips when edge down). **102 passed, 1 skipped.**
- **Non-goals kept:** no Rust rewrite of vibe19; pandas stays canonical for charts/complex FC/ML; codebases stay separate (integrate via historian + HTTP + shared YAML).

---

## 2026-07-08 — Open-FDD cookbook rule engine (data-model-driven)

**Done:**
- **Full cookbook catalog** — `cookbook_rules.py`: all Open-FDD pandas cookbook rules coded declaratively (SV sweep, FC1–FC15, AHU extras, ECON-1–5, VAV, central plant, heat pump, weather, trim, extended). 48 rules; each carries required logical roles, imperial equation text, tunable slider params, confirm-seconds, and a pure compute fn returning a raw fault mask.
- **RDF-driven engine** — `cookbook_engine.py`: layered role resolution (RDF `pointRole` → `economizer_point_mapping.json` → physical-name heuristics, with column-collision guard). Builds a logical frame per equipment, merges Open-Meteo (dry-bulb/RH/dew point), runs every rule for the equipment kind, confirms faults, rolls up fault-hours. Rules missing points report **"Not in data model"** so the UI still shows the equation + sliders.
- **ECON-3 dew-point gate** — uses Open-Meteo OA dew point when present (economizer available if OA dry-bulb 35–72 °F AND dew point < 60 °F); imperial fallback (OAT < 63 °F) when weather absent.
- **API** — `GET/POST /api/cookbook/{page_id}` (per-page equipment + rules; POST re-runs with tuned `params_by_rule`), `GET /api/cookbook/catalog`. Page→equipment mapping in `cookbook_engine.page_targets`.
- **UI** — `static/dashboard_cookbook.js` + `.cookbook-section` mount auto-populates each category tab with cookbook fault cards grouped by family, live sliders, and muted not-applicable cards. `test_cookbook.py` (14 tests) covers role resolution, applicability, ECON-3 dew-point vs fallback, representative masks.
- **How to add a rule:** append a `CookbookRule` to `RULES` in `cookbook_rules.py` (compute fn + required roles + params). It auto-appears on the matching category tab; unresolved points show "not in data model".

---

## 2026-07-08 — Custom rule/ML lab + Flask → FastAPI migration

**Done:**
- **Custom rule plugin system** — `rules/` (Pydantic `RuleManifest`/`RuleContext`/`RuleResult`, `confirm_fault` helper, disk-based `RuleRegistry`); example plugins: `custom_sat_hunting` (pandas) + `ml_oat_residual` (sklearn IsolationForest w/ z-score fallback). Frontend rules lab (`static/dashboard_rules.js`) + `custom_rules` page.
- **Migrated Flask → FastAPI** — `app.py` is now an ASGI FastAPI app; RDF blueprint ported to `haystack_rdf/fastapi_routes.py`; deleted `flask_routes.py`. Typed request bodies in `api_models.py`; sessions via Starlette `SessionMiddleware`; `/docs` + `/openapi.json` live. Entry: `asgi.py` (Uvicorn / Gunicorn `UvicornWorker`); Dockerfiles + `requirements.txt` updated. Heavy pandas endpoints stay sync → run in threadpool; cache behavior unchanged.
- **Why FastAPI, not for speed:** API-first/forkable contract, Pydantic validation, auto OpenAPI, aligns with open-fdd bridge. See `docs/PERFORMANCE_AND_LOADING.md` (Flask vs FastAPI).
- **61 pytest green** after migration (incl. RDF routes via `fastapi.testclient`).

---

## 2026-07-08 — Dashboard mega-reorg + Arrow/plugins roadmap

**Done:**
- ECM cards, light/dark theme, engineer PIN + package lock, site occupancy settings
- `page_registry`, dynamic AHU nav, chiller/boiler split, motor runtime, analytics export
- 61 pytest green (incl. registry, occupancy, auth, rollups)
- **`docs/ROADMAP_ARROW_PLUGINS_ML.md`** — Arrow/DuckDB next steps, custom rule plugins, Pydantic boundaries, ML hooks, `HistorySource` protocol

**Next (planned):** Pydantic API schemas → `HistorySource` → DuckDB zone experiment → rule plugin registry.

---

**Done:**
- **`timeseries_grid.py`** — sub-5-min historian → 5-min means; ≥5-min unchanged; `effective_poll_seconds` on DataFrame
- **Feather cache**, fast path discovery, HTML body cache, shell-first Flask UX
- **Docker deploy** replaces PythonAnywhere (`Dockerfile`, `docker-compose.yml`, `DEPLOY.md`)
- **Agent spec revision** — AI quick rules in `vibe19_agent_spec/AGENTS.md`, updated skills, `PERFORMANCE_AND_LOADING.md`, checkpoints
- **40/40 pytest** green (timeseries, economizer, haystack, env bootstrap)

**AI agents:** start at `vibe19_agent_spec/AGENTS.md` quick rules; never SPARQL on HTTP hot path.

---

## 2026-07-07 — Haystack RDF / SPARQL data model

**Done:**
- New package `haystack_rdf/` — Haystack TTL (not Brick), rdflib SPARQL, JSON import/export
- CSV bootstrap → `data/rdf/{BUILDING}/model.json` + `data_model.ttl` (1917 points on BUILDING_100)
- Flask routes `/api/rdf/*` + `/data_model.html` (plain JS SPARQL explorer, prebuilt queries)
- `economizer_fdd_engine.resolve_columns()` — SPARQL-first with JSON fallback
- Tests: `test_haystack_rdf.py` (9 tests); **39/39 total** dashboard pytest green
- Skill: `vibe19-haystack-rdf/SKILL.md`

**Try:** http://127.0.0.1:5000/data_model.html → Bootstrap from CSV

**Next:** dynamic AHU pages from SPARQL equipment discovery; SPARQL fault scope

---

## 2026-07-07 — Template intent documented

**Product framing:** App 19 is a forkable dashboard template; BUILDING_100/50 are reference examples only. Added [`TEMPLATE.md`](TEMPLATE.md), template-first principle in `AGENTS.md`, reordered `BUILD_CHECKPOINTS.md` (template vs reference-example work).

---

## 2026-07-07 — Performance + Open-Meteo economizer tuning *(reference example: BUILDING_100)*

**Building:** `BUILDING_100` · data via `HVAC_DATA_ROOT` (external, not in git)

**Done:**
- Open-Meteo economizer OK logic in `economizer_fdd_engine.py` (DP &lt; 60°F, OAT band, min OA ~20%, full econ ~95%)
- Revised ECON-2, NOT_ECONOMIZING, MECH_COOLING; free-cool opportunity / econ2 / econ3 faults in `generate_dashboard.py`
- New charts: OAT vs SAT scatter, CHWS vs OAT, HWS vs OAT, duct static violin; ECM5 chiller-only fix
- Analyst tunables: `economizer_low_limit_f`, `oa_min_expected_pct`, `oa_max_economizer_pct`, dew point on more pages
- **`dashboard_cache.py`** — param-keyed context cache, CSV mtime invalidation, per-page lazy `compute_context(page_id=...)`, background prewarm, economizer diagnostics HTML skip
- **`app.py`** wired to cache; AHU pages ~0.15s compute vs ~8s full pipeline
- BUILDING_100: 43 VAV per-box folders merged; mixed grid in manifest (AHU/weather 15-min, VAV 5-min); `validate_data.py` → GO

**Tests:** 30/30 (`test_economizer_diagnostics.py`, `test_sensor_qa.py`)

**Known gaps (BUILDING_100):**
- 74 mapped VAV IDs still lack per-box CSV folders (space temp only in AHU wide)
- 7 VAV folders not in `vav_to_ahu_simple.csv`
- 2 AHU zone columns missing from `history_wide.csv`
- `BUILDING_50` not refreshed

**Next:** VAV terminal FDD (cookbook §5) · Building 50 parity · rule catalog index page
