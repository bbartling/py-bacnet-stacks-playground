"""ECMs + capital plan guardrails (folded Easy Buttons)."""

from __future__ import annotations

import json
from importlib.util import find_spec
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from wattlab.finance import capital_plan, measure_economics, plan_to_csv
from wattlab.measures.measure_sets import expand_measure_set, list_measure_sets
from wattlab.studio.g14_history import assign_run_numbers, iter_g14_history, pick_best_g14_run
from wattlab.studio.proxies import DEFAULT_MEASURE_COSTS, estimate_proxy_savings
from wattlab.studio.workspace import reports_dir, runs_dir


def _load_run_report(run_dir: Path | str | None) -> dict[str, Any]:
    if not run_dir:
        return {}
    root = Path(run_dir)
    for name in ("report.json", "wattlab_report.json", "calibration_scorecard.json"):
        p = root / name
        if p.is_file():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                return data if isinstance(data, dict) else {}
            except (OSError, json.JSONDecodeError, TypeError):
                continue
    return {}


def _enrich_profile_for_proxies(profile: dict[str, Any]) -> dict[str, Any]:
    """Merge answers / hard_size nameplate into a profile copy for ESCO bins."""
    out = dict(profile)
    answers = st.session_state.get("studio_answers")
    if isinstance(answers, dict):
        for key in (
            "cooling_tons",
            "fan_hp",
            "supply_fan_hp",
            "conditioned_floor_area_ft2",
            "floor_area_ft2",
        ):
            if out.get(key) is None and answers.get(key) is not None:
                out[key] = answers[key]
    hard = st.session_state.get("studio_hard_size")
    if isinstance(hard, dict) and not isinstance(out.get("hard_size"), dict):
        out["hard_size"] = hard
    return out


def _traffic_light(*, verdict: str | None, has_ep: bool) -> str:
    """🟢 in-line · 🟡 method gap / ESCO-only · 🔴 investigate / implausible."""
    if not has_ep:
        return "🟡"
    canon = str(verdict or "").upper()
    legacy = str(verdict or "").lower()
    if canon == "IN_LINE" or legacy == "in_line":
        return "🟢"
    if (
        canon == "REASONABLE_METHOD_DIFFERENCE"
        or canon == "INSUFFICIENT_EVIDENCE"
        or legacy == "investigate"
    ):
        return "🟡"
    return "🔴"


def _render_baseline_run_picker() -> None:
    """Selectbox of Twin runs; default = best G14; store studio_ecm_baseline_run."""
    st.subheader("Twin baseline run")
    st.caption(
        "ECMs savings/deliverable context follows the selected Twin publish. "
        "Prefer a run with ``savings_by_measure`` so Compare is not all YELLOW. "
        "Default is best G14 (PASS preferred, else lowest |NMBE|+CVRMSE)."
    )
    try:
        rows = assign_run_numbers(iter_g14_history(runs_dir(), limit=40))
    except Exception:
        rows = []
    if not rows:
        st.info("No published Twin runs yet — calibrate on Twin first.")
        return

    best = pick_best_g14_run(rows)
    opts = [str(r["dir"]) for r in rows if r.get("dir")]
    by_dir = {str(r["dir"]): r for r in rows if r.get("dir")}

    # Annotate which runs have E+ measure savings (BUG-034)
    has_sbm: dict[str, bool] = {}
    for d in opts:
        rep = _load_run_report(d)
        has_sbm[d] = bool(rep.get("savings_by_measure"))

    stored = st.session_state.get("studio_ecm_baseline_run")
    if stored and str(stored) in opts:
        default_dir = str(stored)
    elif best and best.get("dir"):
        default_dir = str(best["dir"])
    else:
        default_dir = opts[-1] if opts else None
    # Prefer ECM-capable run when default lacks savings_by_measure
    if default_dir and not has_sbm.get(default_dir):
        with_sbm = [d for d in opts if has_sbm.get(d)]
        if with_sbm:
            default_dir = with_sbm[-1]

    if default_dir and "studio_ecm_baseline_pick" not in st.session_state:
        st.session_state["studio_ecm_baseline_pick"] = default_dir
    cur = st.session_state.get("studio_ecm_baseline_pick")
    if cur is not None and cur not in opts:
        st.session_state.pop("studio_ecm_baseline_pick", None)
        if default_dir:
            st.session_state["studio_ecm_baseline_pick"] = default_dir

    def _label(d: str) -> str:
        r = by_dir.get(d) or {}
        n = r.get("run")
        rid = r.get("run_id") or Path(d).name
        pf = r.get("pass_fail") or "—"
        tag = " · best G14" if best and str(best.get("dir")) == d else ""
        ecm = " · E+ measures" if has_sbm.get(d) else " · ESCO-only"
        return f"#{n} · {rid} · {pf}{tag}{ecm}" if n is not None else f"{rid} · {pf}{tag}{ecm}"

    pick = st.selectbox(
        "Baseline Twin run",
        options=opts,
        format_func=_label,
        key="studio_ecm_baseline_pick",
    )
    if pick:
        st.session_state["studio_ecm_baseline_run"] = pick
        report = _load_run_report(pick)
        score = {}
        sp = Path(pick) / "calibration_scorecard.json"
        if sp.is_file():
            try:
                score = json.loads(sp.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, TypeError):
                score = {}
        if report:
            st.session_state["studio_report"] = {
                **(st.session_state.get("studio_report") or {}),
                **report,
            }
        meta = by_dir.get(pick) or {}
        st.caption(
            f"Active ECM baseline: #{meta.get('run')} · {meta.get('run_id')} · "
            f"G14={meta.get('pass_fail') or (score.get('utility_bills') or {}).get('pass_fail') or '—'} "
            f"· `{Path(pick).name}`"
        )
        if not has_sbm.get(pick):
            st.warning(
                "This Twin run has no ``savings_by_measure`` — notebook Compare will be "
                "mostly YELLOW (ESCO-only). Pick a run tagged **E+ measures** when available."
            )


def _render_engineering_notebook(profile: dict[str, Any]) -> None:
    """Primary ECM deliverable: package Excel notebook (preview + download)."""
    from wattlab.notebooks import (
        build_and_save_notebook,
        list_notebook_packages,
        preview_sheet_rows,
    )
    from wattlab.studio.ecm_scenario import (
        default_ecm_scenario_path,
        load_ecm_scenario,
        save_ecm_scenario,
    )

    st.subheader("Engineering notebook (Excel)")
    st.caption(
        "Primary deliverable: least→radical Excel package (ESCO vs E+ + ROI). "
        "Preview shows formulas as text + ``npv_usd_at_build`` cache (open Excel to evaluate). "
        "Agents: `wattlab notebook build|prefill|validate|summarize`."
    )
    st.markdown(
        "[ESCO formula map (GitHub)]"
        "(https://github.com/bbartling/py-bacnet-stacks-playground/blob/develop/"
        "vibe_code_apps_20/docs/ESCO_SPREADSHEET_CALCS.md)"
    )
    pkgs = list_notebook_packages()
    by_id = {p.id: p for p in pkgs}
    labels = {p.id: p.label for p in pkgs}
    pick = st.selectbox(
        "Package",
        [p.id for p in pkgs],
        format_func=lambda k: labels.get(k, k),
        key="ecm_notebook_package",
    )
    pkg = by_id[pick]
    st.caption(f"{pkg.honesty} · {len(pkg.measure_ids)} measures · catalog `{pkg.catalog_package}`")

    out_dir = reports_dir() / "notebooks"
    if st.button("Build / refresh notebook", type="primary", key="ecm_notebook_build"):
        try:
            proxy_profile = _enrich_profile_for_proxies(profile)
            report = st.session_state.get("studio_report") or {}
            run = st.session_state.get("studio_ecm_baseline_run")
            if run and not report.get("savings_by_measure"):
                report = {**report, **_load_run_report(run)}
            written = build_and_save_notebook(
                pick,
                out_dir,
                profile=proxy_profile,
                report=report if isinstance(report, dict) else {},
                write_manifest=True,
            )
            st.session_state["studio_notebook_path"] = str(written["xlsx"])
            st.session_state["studio_notebook_manifest"] = str(written.get("manifest") or "")
            from wattlab.notebooks.builder import validate_notebook

            v = validate_notebook(written["xlsx"])
            for w in v.get("warnings") or []:
                st.warning(w)
            # Persist for agents
            scen = load_ecm_scenario()
            scen["notebook_package_id"] = pick
            scen["notebook_path"] = str(written["xlsx"])
            scen["selected_ecm_ids"] = list(pkg.measure_ids)
            save_ecm_scenario(scen)
            st.success(f"Notebook → {written['xlsx']}")
        except Exception as exc:
            st.error(f"Notebook build failed: {exc}")
            return

    xlsx = st.session_state.get("studio_notebook_path")
    if not xlsx or not Path(str(xlsx)).is_file():
        # Autoload if package file already on disk
        candidate = out_dir / f"{pick}.xlsx"
        if candidate.is_file():
            xlsx = str(candidate)
            st.session_state["studio_notebook_path"] = xlsx
    if xlsx and Path(str(xlsx)).is_file():
        path = Path(str(xlsx))
        st.caption(
            "Preview uses formula text (not Excel-calculated). "
            "Use ``npv_usd_at_build`` / Inputs values for agent numbers; open Excel for live NPV."
        )
        tabs = st.tabs(["Inputs", "Compare", "ROI_Capital"])
        for tab, sheet in zip(tabs, ("Inputs", "Compare", "ROI_Capital")):
            with tab:
                rows = preview_sheet_rows(path, sheet, max_rows=50, data_only=False)
                if not rows:
                    st.caption(f"Sheet `{sheet}` empty or missing.")
                else:
                    st.dataframe(
                        pd.DataFrame(rows[1:], columns=rows[0] if rows else None),
                        width="stretch",
                        hide_index=True,
                    )
        st.download_button(
            "Download engineering notebook (.xlsx)",
            data=path.read_bytes(),
            file_name=path.name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="ecm_dl_notebook_xlsx",
            type="primary",
        )
        man = path.parent / f"{path.stem}.notebook_manifest.json"
        if man.is_file():
            st.download_button(
                "Download notebook_manifest.json (agents)",
                data=man.read_bytes(),
                file_name=man.name,
                mime="application/json",
                key="ecm_dl_notebook_manifest",
            )
        st.caption(f"Also on disk: `{path}` · scenario → `{default_ecm_scenario_path()}`")


def render() -> None:
    st.header("ECMs — engineering notebooks")
    st.caption(
        "Primary deliverable is an Excel notebook per package (ESCO vs EnergyPlus + ROI). "
        "Easy Buttons / capital-plan details live under Advanced."
    )

    profile = st.session_state.get("studio_profile")
    if not profile:
        answers = st.session_state.get("studio_answers")
        st.info(
            "Resolve a profile on **Twin / calibrate** first — or bootstrap with "
            "`answers_path` so Re-apply builds `studio_profile` automatically. "
            "Agents: `wattlab notebook build --package controls_first --out reports/notebooks/`."
        )
        if isinstance(answers, dict):
            st.caption(
                f"answers.json present (type={answers.get('building_type')}, "
                f"city={answers.get('city')}) — Re-apply bootstrap to unlock ECMs."
            )
        return

    _render_baseline_run_picker()
    st.divider()
    _render_engineering_notebook(profile)
    st.divider()

    with st.expander(
        "Advanced — Easy Buttons, measure sets, capital plan, client DOCX",
        expanded=False,
    ):
        from wattlab.studio.pages.ecm_easy_buttons import render as render_easy

        render_easy(profile=profile, proxy_estimator=estimate_proxy_savings)
        st.divider()
        st.subheader("Measure set + proxy pricing")
        st.caption("Optional legacy path — Engineering notebook above is preferred for deliverables.")
        sets = list_measure_sets()
        set_ids = [s["id"] for s in sets] or ["best"]
        labels = {s["id"]: f"{s['label']} — {', '.join(s['measure_ids'])}" for s in sets}
        mset = st.selectbox(
            "Measure set",
            set_ids,
            format_func=lambda k: labels.get(k, k),
            index=max(0, len(set_ids) - 1),
            key="ecm_measure_set",
        )
        if st.button("Build measures + proxies", key="ecm_build_measures"):
            measure_rows = expand_measure_set(str(mset))
            ids = [str(m.get("measure_id")) for m in measure_rows if m.get("measure_id")]
            # Prefer Easy Button scenario if present
            scenario_ids = st.session_state.get("ecm_easy__scenario_ids") or st.session_state.get(
                "ecm_easy_scenario_ids"
            )
            if not scenario_ids:
                # namespaced_key may use a different separator — also check common keys
                for k, v in st.session_state.items():
                    if "scenario_ids" in str(k) and isinstance(v, list) and v:
                        scenario_ids = v
                        break
            if scenario_ids:
                ids = list(dict.fromkeys([str(x) for x in scenario_ids] + ids))
                measure_rows = [{"measure_id": mid} for mid in ids]
            proxy_profile = _enrich_profile_for_proxies(profile)
            proxies = estimate_proxy_savings(proxy_profile, ids)
            from wattlab.studio.ecm_roi import rows_to_cost_map, seed_roi_cost_rows

            area0 = float(
                proxy_profile.get("conditioned_floor_area_ft2")
                or proxy_profile.get("floor_area_ft2")
                or 50000.0
            )
            roi_rows = seed_roi_cost_rows(
                ids,
                floor_area_ft2=area0,
                existing=st.session_state.get("studio_ecm_roi_models"),
            )
            costs = rows_to_cost_map(roi_rows)
            # Blend with hard-coded lump sums when ROI model is tiny
            for mid in ids:
                if costs.get(mid, 0) <= 0:
                    costs[mid] = DEFAULT_MEASURE_COSTS.get(mid, 10000.0)
            st.session_state["studio_measures"] = measure_rows
            st.session_state["studio_proxies"] = proxies
            st.session_state["studio_costs"] = costs
            st.session_state["studio_ecm_roi_rows"] = roi_rows
            st.session_state["studio_measure_set"] = str(mset)
            # Default cherry-pick to first measure only (avoid dumping full capital stack)
            if ids and not st.session_state.get("studio_ecm_cherry_pick"):
                st.session_state["studio_ecm_cherry_pick"] = [ids[0]]
            st.success(f"{len(ids)} measures priced (proxy + $/ft² ROI seed).")

        measure_rows = st.session_state.get("studio_measures") or []
        if measure_rows and isinstance(measure_rows[0], str):
            measure_rows = [{"measure_id": m} for m in measure_rows]
        measures = [str(m.get("measure_id")) for m in measure_rows if isinstance(m, dict) and m.get("measure_id")]
        # Also pull Easy Button scenario into comparison when measures empty
        if not measures:
            for k, v in st.session_state.items():
                if "scenario_ids" in str(k) and isinstance(v, list) and v:
                    measures = [str(x) for x in v]
                    break
        proxies = st.session_state.get("studio_proxies") or {}
        costs = st.session_state.get("studio_costs") or {}

        cherry: list[str] = []
        if measures:
            st.markdown("#### Cherry-pick package")
            st.caption(
                "Capital plan + ROI rollup use only the measures below. "
                "Start with one ECM, compare ESCO ↔ EnergyPlus, then add more."
            )
            stored_cherry = st.session_state.get("studio_ecm_cherry_pick")
            cur = [m for m in (stored_cherry or []) if m in measures]
            if not cur:
                cur = [measures[0]]
            st.session_state["studio_ecm_cherry_pick"] = cur
            cherry = st.multiselect(
                "Active measures (capital plan)",
                options=measures,
                key="studio_ecm_cherry_pick",
                help="Deselect everything you do not want in NPV / payback totals.",
            )
            c_run, c_hint = st.columns([1, 2])
            with c_run:
                if st.button("Recalc ESCO for cherry-pick", key="ecm_recalc_cherry"):
                    if not cherry:
                        st.warning("Select at least one measure.")
                    else:
                        proxy_profile = _enrich_profile_for_proxies(profile)
                        from wattlab.studio.proxies import resolve_proxy_inputs

                        inputs = resolve_proxy_inputs(proxy_profile)
                        new_px = estimate_proxy_savings(proxy_profile, cherry)
                        proxies = {**(st.session_state.get("studio_proxies") or {}), **new_px}
                        st.session_state["studio_proxies"] = proxies
                        src = ", ".join(inputs.get("sources") or [])
                        st.success(
                            f"ESCO proxies refreshed for {len(cherry)} measure(s) "
                            f"(inputs: {src}; area={inputs['area_ft2']:,.0f} ft²"
                            + (
                                f", {inputs['cooling_tons']:g} tons"
                                if inputs.get("cooling_tons")
                                else ""
                            )
                            + (
                                f", {inputs['fan_hp']:g} HP"
                                if inputs.get("fan_hp")
                                else ""
                            )
                            + ")."
                        )
            with c_hint:
                st.caption(
                    "🟢 in-line · 🟡 method difference or ESCO-only · 🔴 investigate / implausible"
                )

        if measures:
            from wattlab.crosscheck import crosscheck_measure

            rows = []
            report = st.session_state.get("studio_report") or {}
            ep_by = {}
            for s in report.get("savings_by_measure") or []:
                mid = s.get("measure_id")
                vs = (s.get("vs_previous") or s.get("vs_baseline") or {})
                if mid:
                    ep_by[mid] = vs
            focus = cherry or measures
            for mid in measures:
                p = proxies.get(mid) or {}
                ep = ep_by.get(mid) or {}
                esco_kwh = p.get("savings_kwh")
                esco_therms = p.get("savings_therms")
                ep_kwh = ep.get("kwh_saved")
                ep_therms = ep.get("therms_saved")
                has_ep = ep_kwh is not None or ep_therms is not None
                xc = crosscheck_measure(
                    measure_id=mid,
                    ep_savings_kwh=None if ep_kwh is None else float(ep_kwh),
                    proxy_savings_kwh=None if esco_kwh is None else float(esco_kwh),
                    ep_savings_therms=None if ep_therms is None else float(ep_therms),
                    proxy_savings_therms=None if esco_therms is None else float(esco_therms),
                )
                ratio = xc.get("agreement_ratio")
                ratio_th = xc.get("agreement_ratio_therms")
                delta_kwh = None
                pct_kwh = None
                if ep_kwh is not None and esco_kwh is not None:
                    delta_kwh = float(ep_kwh) - float(esco_kwh)
                    if abs(float(esco_kwh)) > 1e-9:
                        pct_kwh = 100.0 * delta_kwh / float(esco_kwh)
                delta_therms = None
                pct_therms = None
                if ep_therms is not None and esco_therms is not None:
                    delta_therms = float(ep_therms) - float(esco_therms)
                    if abs(float(esco_therms)) > 1e-9:
                        pct_therms = 100.0 * delta_therms / float(esco_therms)
                verdict = xc.get("verdict_canonical") or xc.get("verdict")
                rows.append({
                    "in_plan": "✓" if mid in focus else "",
                    "light": _traffic_light(verdict=verdict, has_ep=has_ep),
                    "measure_id": mid,
                    "esco_kwh": esco_kwh,
                    "ep_kwh": ep_kwh,
                    "delta_kwh": None if delta_kwh is None else round(delta_kwh, 1),
                    "pct_vs_esco_kwh": None if pct_kwh is None else round(pct_kwh, 1),
                    "esco_therms": esco_therms,
                    "ep_therms": ep_therms,
                    "delta_therms": None if delta_therms is None else round(delta_therms, 1),
                    "pct_vs_esco_therms": None if pct_therms is None else round(pct_therms, 1),
                    "agreement_ratio": ratio,
                    "agreement_ratio_therms": ratio_th,
                    "verdict": verdict,
                    "cost_usd": costs.get(mid),
                })
            st.markdown("#### Selected measures — ESCO spreadsheet vs EnergyPlus")
            st.caption(
                "ESCO = bin-method screening (`wattlab/studio/proxies.py`). "
                "EP = Twin `savings_by_measure` when present. "
                "Δ / % = EP − ESCO (positive ⇒ E+ saves more). "
                "Verdict from `wattlab.crosscheck` (~0.5–2× = reasonable). "
                "Yellow without EP columns means run Twin measure sims before trusting green."
            )
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

        # Capital plan / ROI use cherry-pick when set
        plan_measures = cherry if cherry else measures

        st.divider()
        st.subheader("ROI screening parameters")
        st.caption(
            "Utility rates + discount for NPV. Per-ECM capital uses $/ft² × coverage "
            "below (Liberty-style: set coverage=0.5 when only half the building gets DDC/G36)."
        )
        area = float(
            profile.get("conditioned_floor_area_ft2")
            or profile.get("floor_area_ft2")
            or 50000.0
        )
        bench = st.session_state.get("studio_benchmark_summary") or {}
        if isinstance(bench, dict) and bench.get("campus"):
            area = float(bench["campus"].get("floor_area_ft2") or area)
        rates = profile.get("utility") or {}
        from wattlab.finance import (
            DEFAULT_DISCOUNT_RATE,
            DEFAULT_ESCALATION_RATE,
            DEFAULT_MEASURE_LIFE_YEARS,
        )

        # Prefill package rollup $/ft2 from controls_first band
        cost_usd_per_ft2_default = 3.0
        try:
            from wattlab.benchmarks.costs import load_registry

            bands = {r["scope"]: r for r in load_registry()}
            if "controls_first" in bands:
                cost_usd_per_ft2_default = float(bands["controls_first"].get("p50") or 3.0)
        except Exception as exc:
            st.caption(f"Retrofit cost-band prefill unavailable ({exc}); using ${cost_usd_per_ft2_default:g}/ft² default.")

        r1, r2, r3 = st.columns(3)
        with r1:
            elec = st.number_input(
                "Elec $/kWh",
                min_value=0.01,
                max_value=1.0,
                value=float(rates.get("elec_usd_per_kwh") or 0.12),
                step=0.01,
                key="ecm_roi_elec",
            )
            gas = st.number_input(
                "Gas $/therm",
                min_value=0.1,
                max_value=5.0,
                value=float(rates.get("gas_usd_per_therm") or 0.80),
                step=0.05,
                key="ecm_roi_gas",
            )
        with r2:
            discount = st.number_input(
                "Discount rate",
                min_value=0.0,
                max_value=0.2,
                value=float(DEFAULT_DISCOUNT_RATE),
                step=0.005,
                format="%.3f",
                key="ecm_roi_discount",
            )
            escalation = st.number_input(
                "Utility escalation",
                min_value=0.0,
                max_value=0.1,
                value=float(DEFAULT_ESCALATION_RATE),
                step=0.005,
                format="%.3f",
                key="ecm_roi_escalation",
            )
        with r3:
            life_years = st.number_input(
                "Measure life (yr)",
                min_value=5,
                max_value=40,
                value=int(DEFAULT_MEASURE_LIFE_YEARS),
                key="ecm_roi_life",
            )
            usd_per_ft2 = st.number_input(
                "Fallback package $/ft²",
                min_value=0.0,
                max_value=100.0,
                value=float(cost_usd_per_ft2_default),
                step=0.25,
                key="ecm_roi_usd_ft2",
                help="Used only when a measure has no per-ECM $/ft² / fixed cost.",
            )
        st.caption(f"Floor area for $/ft² math: {area:,.0f} ft²")

        # --- Per-ECM ROI cost calculator ---
        if plan_measures:
            from wattlab.studio.ecm_roi import (
                implementation_cost_usd,
                rows_to_cost_map,
                rows_to_models,
                seed_roi_cost_rows,
            )

            st.markdown("#### Per-ECM ROI cost calculator")
            st.caption(
                "Prefills are screening defaults for the **cherry-picked** set. Edit **usd_per_ft2** and "
                "**coverage_fraction** (0–1 of floor area) or set **fixed_usd** for a "
                "lump-sum quote. Example: G36 needs 50% DDC → coverage=0.5."
            )
            seed = seed_roi_cost_rows(
                plan_measures,
                floor_area_ft2=area,
                existing=st.session_state.get("studio_ecm_roi_models"),
            )
            edited = st.data_editor(
                pd.DataFrame(seed),
                width="stretch",
                hide_index=True,
                num_rows="fixed",
                column_config={
                    "measure_id": st.column_config.TextColumn("ECM", disabled=True),
                    "usd_per_ft2": st.column_config.NumberColumn("$/ft²", min_value=0.0, step=0.05, format="%.2f"),
                    "coverage_fraction": st.column_config.NumberColumn(
                        "Coverage", min_value=0.0, max_value=1.0, step=0.05, format="%.2f",
                        help="Fraction of building floor area that receives this ECM",
                    ),
                    "applicable_ft2": st.column_config.NumberColumn("ft² applied", disabled=True),
                    "fixed_usd": st.column_config.NumberColumn(
                        "Fixed $ (optional)", min_value=0.0, step=1000.0, format="%.0f",
                    ),
                    "implementation_cost_usd": st.column_config.NumberColumn(
                        "Cost $", disabled=True, format="%.0f"
                    ),
                    "note": st.column_config.TextColumn("Note", width="large"),
                },
                key="ecm_roi_cost_editor",
            )
            # Recompute costs from edited $/ft2 + coverage / fixed
            recomputed: list[dict] = []
            for _, r in edited.iterrows():
                mid = str(r["measure_id"])
                usd = float(r.get("usd_per_ft2") or 0.0)
                cov = float(r.get("coverage_fraction") or 1.0)
                fixed_raw = r.get("fixed_usd")
                fixed_f = None
                if fixed_raw is not None and not (isinstance(fixed_raw, float) and pd.isna(fixed_raw)):
                    try:
                        fv = float(fixed_raw)
                        if fv > 0:
                            fixed_f = fv
                    except (TypeError, ValueError):
                        fixed_f = None
                cost = implementation_cost_usd(
                    floor_area_ft2=area,
                    usd_per_ft2=usd,
                    coverage_fraction=cov,
                    fixed_usd=fixed_f,
                )
                recomputed.append(
                    {
                        "measure_id": mid,
                        "usd_per_ft2": usd,
                        "coverage_fraction": cov,
                        "applicable_ft2": round(area * max(0.0, min(1.0, cov)), 0),
                        "fixed_usd": fixed_f,
                        "implementation_cost_usd": round(cost, 0),
                        "note": str(r.get("note") or ""),
                    }
                )
            st.session_state["studio_ecm_roi_rows"] = recomputed
            st.session_state["studio_ecm_roi_models"] = rows_to_models(recomputed)
            costs = rows_to_cost_map(recomputed)
            st.session_state["studio_costs"] = costs
            st.dataframe(
                pd.DataFrame(recomputed)[
                    ["measure_id", "applicable_ft2", "implementation_cost_usd", "note"]
                ],
                width="stretch",
                hide_index=True,
            )

        st.divider()
        st.subheader("Capital plan + guardrails")
        if not plan_measures:
            st.info(
                "Cherry-pick at least one measure above (or Build measures / Easy Buttons) "
                "to roll up capital plan."
            )
            return

        st.caption(f"Capital plan includes {len(plan_measures)} measure(s): {', '.join(plan_measures)}")
        proxy_profile = _enrich_profile_for_proxies(profile)
        econ_rows = []
        for mid in plan_measures:
            p = proxies.get(mid) or {}
            if mid not in proxies:
                # lazy proxy if engineer only checked Easy Buttons
                try:
                    proxies.update(estimate_proxy_savings(proxy_profile, [mid]))
                    p = proxies.get(mid) or {}
                    st.session_state["studio_proxies"] = proxies
                except Exception:
                    p = {}
            cost = float(costs.get(mid) or 0.0)
            if cost <= 0:
                cost = (usd_per_ft2 * area) / max(len(plan_measures), 1)
            econ_rows.append(
                measure_economics(
                    measure_id=mid,
                    implementation_cost_usd=cost,
                    kwh_saved=float(p.get("savings_kwh") or 0.0),
                    therms_saved=float(p.get("savings_therms") or 0.0),
                    elec_rate_usd_per_kwh=float(elec),
                    gas_rate_usd_per_therm=float(gas),
                    discount_rate=float(discount),
                    escalation_rate=float(escalation),
                    measure_life_years=int(life_years),
                )
            )
        # Prefer EnergyPlus savings when a report exists
        report = st.session_state.get("studio_report") or {}
        ep_by = {}
        for s in report.get("savings_by_measure") or []:
            mid = s.get("measure_id")
            vs = (s.get("vs_previous") or s.get("vs_baseline") or {})
            if mid:
                ep_by[mid] = vs
        if ep_by:
            for row in econ_rows:
                mid = row.get("measure_id")
                if mid in ep_by:
                    row["kwh_saved"] = float(ep_by[mid].get("kwh_saved") or row.get("kwh_saved") or 0)
                    row["therms_saved"] = float(ep_by[mid].get("therms_saved") or row.get("therms_saved") or 0)
                    if ep_by[mid].get("peak_demand_kw_delta") is not None:
                        row["peak_demand_kw_delta"] = ep_by[mid]["peak_demand_kw_delta"]

        # Show demand columns from report when present
        demand_preview = []
        for s in report.get("savings_by_measure") or []:
            if s.get("peak_demand_kw") is not None:
                demand_preview.append(
                    {
                        "measure_id": s.get("measure_id"),
                        "peak_demand_kw": s.get("peak_demand_kw"),
                        "vs_baseline_kw": (s.get("vs_baseline") or {}).get("peak_demand_kw_delta"),
                    }
                )
        if demand_preview:
            st.markdown("**Peak demand (kW)** from EnergyPlus results")
            st.dataframe(pd.DataFrame(demand_preview), width="stretch", hide_index=True)

        plan = capital_plan(econ_rows)
        st.session_state["studio_capital_plan"] = plan

        from wattlab.benchmarks.guardrails import gate_capital_plan

        property_type = str(profile.get("building_type") or profile.get("property_type") or "office")
        site_eui = None
        if isinstance(bench, dict) and bench.get("campus"):
            site_eui = bench["campus"].get("site_eui_kbtu_ft2")
        gate = gate_capital_plan(
            plan,
            property_type=property_type,
            floor_area_ft2=area,
            site_eui_kbtu_ft2=site_eui,
        )
        st.session_state["studio_guardrail_gate"] = gate

        if gate["verdict"] == "INVESTIGATE":
            st.error(f"Benchmark gate: INVESTIGATE — {gate['investigate_count']} check(s)")
        else:
            st.success("Benchmark gate: PUBLISH")
        with st.expander("Guardrail checks", expanded=gate["verdict"] == "INVESTIGATE"):
            st.dataframe(
                pd.DataFrame([
                    {"check": c["check"], "status": c["status"], "detail": c["detail"]}
                    for c in gate["checks"]
                ]),
                width="stretch",
                hide_index=True,
            )

        totals = plan["totals"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total cost", f"${totals['implementation_cost_usd']:,.0f}")
        c2.metric("Annual savings", f"${totals['annual_cost_saved_usd']:,.0f}")
        pb = totals.get("blended_simple_payback_years")
        c3.metric("Blended payback", f"{pb:.1f} yr" if pb is not None else "—")
        c4.metric("Portfolio NPV", f"${totals['npv_usd']:,.0f}")
        # Portfolio ROI from lifetime savings vs cost (screening)
        life_sav = sum(float(m.get("lifetime_savings_usd") or 0) for m in plan["measures"])
        total_cost = float(totals.get("implementation_cost_usd") or 0)
        if total_cost > 0 and life_sav:
            st.metric("Portfolio ROI over life", f"{(life_sav - total_cost) / total_cost * 100:.0f}%")

        st.dataframe(
            pd.DataFrame(plan["measures"]).drop(columns=["assumptions"], errors="ignore"),
            width="stretch",
            hide_index=True,
        )
        out = reports_dir() / "capital_plan.json"
        out.write_text(json.dumps(plan, indent=2), encoding="utf-8")
        scenario = {
            "measures": measures,
            "proxies": proxies,
            "costs": costs,
            "ecm_roi_models": st.session_state.get("studio_ecm_roi_models") or {},
            "ecm_roi_rows": st.session_state.get("studio_ecm_roi_rows") or [],
            "roi_params": {
                "elec_usd_per_kwh": elec,
                "gas_usd_per_therm": gas,
                "discount_rate": discount,
                "escalation_rate": escalation,
                "measure_life_years": life_years,
                "usd_per_ft2": usd_per_ft2,
                "floor_area_ft2": area,
            },
            "capital_plan_totals": totals,
            "guardrail_gate": {
                "verdict": gate.get("verdict"),
                "investigate_count": gate.get("investigate_count"),
                "checks": gate.get("checks"),
            },
        }
        (reports_dir() / "ecm_scenario_results.json").write_text(
            json.dumps(scenario, indent=2), encoding="utf-8"
        )
        d1, d2, d3 = st.columns(3)
        d1.download_button(
            "Download capital plan CSV",
            data=plan_to_csv(plan),
            file_name="wattlab_capital_plan.csv",
            mime="text/csv",
            key="ecm_dl_csv",
        )
        d2.download_button(
            "Download capital plan JSON",
            data=json.dumps(plan, indent=2),
            file_name="wattlab_capital_plan.json",
            mime="application/json",
            key="ecm_dl_json",
        )
        d3.download_button(
            "Download ECM scenario results",
            data=json.dumps(scenario, indent=2),
            file_name="ecm_scenario_results.json",
            mime="application/json",
            key="ecm_dl_scenario",
        )
        st.caption(f"Also written to `{out}` for agents.")

        st.subheader("Client energy-model package")
        st.caption(
            "Optional Twin zip (report + results xlsx). Prefer the Engineering notebook above for ECM ROI. "
            "DOCX is off by default."
        )
        docx_available = find_spec("docx") is not None
        include_docx = st.checkbox(
            "Include client DOCX",
            value=False,
            disabled=not docx_available,
            key="ecm_include_client_docx",
        )
        if not docx_available:
            st.caption("Client DOCX is unavailable until the optional `python-docx` dependency is installed.")
        if st.button("Build client package from ECM report", key="ecm_build_deliverable"):
            from wattlab.deliverables import package_deliverables

            if not report:
                st.warning("No studio_report yet — run Twin / easy-button first.")
            else:
                rid = report.get("run_id") or "ecm_report"
                dest = reports_dir() / f"deliverable_{rid}"
                try:
                    sc = {
                        "run_id": rid,
                        "status": "screening",
                        "annual": ((report.get("result_records") or [{}])[0] or {}).get("annual"),
                        "weather_suitability": report.get("weather_suitability"),
                        "prototype_area_scale": report.get("prototype_area_scale"),
                        "sizing_scenario": report.get("sizing_scenario"),
                        "utility_bills": {},
                    }
                    active_ids = {str(m) for m in (measures or [])}
                    proxy_for_pkg = {
                        k: v
                        for k, v in (proxies or {}).items()
                        if str(k) in active_ids
                    }
                    meta = package_deliverables(
                        out_dir=dest,
                        scorecard=sc,
                        report={**report, "proxy_savings": proxy_for_pkg},
                        profile=profile,
                        include_docx=include_docx,
                    )
                    st.session_state["studio_deliverable"] = meta
                    st.success(f"Package → {meta.get('out_dir')}")
                    if meta.get("docx_note"):
                        st.caption(str(meta["docx_note"]))
                except Exception as exc:
                    st.error(str(exc))
        deliv = st.session_state.get("studio_deliverable") or {}
        if deliv.get("zip_path") and Path(str(deliv["zip_path"])).is_file():
            st.download_button(
                "Download energy-model package (.zip)",
                data=Path(str(deliv["zip_path"])).read_bytes(),
                file_name=Path(str(deliv["zip_path"])).name,
                mime="application/zip",
                key="ecm_dl_deliverable_zip",
            )
