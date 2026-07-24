"""ECMs + capital plan guardrails (folded Easy Buttons)."""

from __future__ import annotations

import json
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


def _render_baseline_run_picker() -> None:
    """Selectbox of Twin runs; default = best G14; store studio_ecm_baseline_run."""
    st.subheader("Twin baseline run")
    st.caption(
        "ECMs savings/deliverable context follows the selected Twin publish. "
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

    stored = st.session_state.get("studio_ecm_baseline_run")
    if stored and str(stored) in opts:
        default_dir = str(stored)
    elif best and best.get("dir"):
        default_dir = str(best["dir"])
    else:
        default_dir = opts[-1] if opts else None

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
        return f"#{n} · {rid} · {pf}{tag}" if n is not None else f"{rid} · {pf}{tag}"

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


def render() -> None:
    st.header("ECMs — measures + capital plan")
    st.caption(
        "Catalog Easy Buttons + measure sets. Capital plan is gated by benchmark "
        "guardrails (PUBLISH / INVESTIGATE)."
    )

    profile = st.session_state.get("studio_profile")
    if not profile:
        answers = st.session_state.get("studio_answers")
        st.info(
            "Resolve a profile on **Twin / calibrate** first — or bootstrap with "
            "`answers_path` so Re-apply builds `studio_profile` automatically. "
            "Agents: `wattlab studio-status --write` then fill answers / "
            "`reports/ecm_scenario.json`."
        )
        if isinstance(answers, dict):
            st.caption(
                f"answers.json present (type={answers.get('building_type')}, "
                f"city={answers.get('city')}) — Re-apply bootstrap to unlock ECMs."
            )
        return

    _render_baseline_run_picker()
    st.divider()

    # --- Easy Buttons catalog ---
    from wattlab.studio.pages.ecm_easy_buttons import render as render_easy

    render_easy(profile=profile, proxy_estimator=estimate_proxy_savings)

    st.divider()
    st.subheader("Measure set + proxy pricing")
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
        proxies = estimate_proxy_savings(profile, ids)
        costs = {mid: DEFAULT_MEASURE_COSTS.get(mid, 10000.0) for mid in ids}
        st.session_state["studio_measures"] = measure_rows
        st.session_state["studio_proxies"] = proxies
        st.session_state["studio_costs"] = costs
        st.session_state["studio_measure_set"] = str(mset)
        st.success(f"{len(ids)} measures priced.")

    measure_rows = st.session_state.get("studio_measures") or []
    if measure_rows and isinstance(measure_rows[0], str):
        measure_rows = [{"measure_id": m} for m in measure_rows]
    measures = [str(m.get("measure_id")) for m in measure_rows if isinstance(m, dict) and m.get("measure_id")]
    proxies = st.session_state.get("studio_proxies") or {}
    costs = st.session_state.get("studio_costs") or {}
    if measures:
        rows = []
        report = st.session_state.get("studio_report") or {}
        ep_by = {}
        for s in report.get("savings_by_measure") or []:
            mid = s.get("measure_id")
            vs = (s.get("vs_previous") or s.get("vs_baseline") or {})
            if mid:
                ep_by[mid] = vs
        for mid in measures:
            p = proxies.get(mid) or {}
            ep = ep_by.get(mid) or {}
            rows.append({
                "measure_id": mid,
                "esco_kwh": p.get("savings_kwh"),
                "esco_therms": p.get("savings_therms"),
                "ep_kwh": ep.get("kwh_saved"),
                "ep_therms": ep.get("therms_saved"),
                "cost_usd": costs.get(mid),
            })
        st.markdown("#### Selected measures — ESCO proxy vs EnergyPlus (when available)")
        st.caption(
            "ESCO column = bin-method screening. EP column = calibrated Twin report "
            "`savings_by_measure` when present. Crosscheck when both exist."
        )
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    st.divider()
    st.subheader("ROI screening parameters")
    st.caption(
        "High-level ESCO economics ($/ft² capital, utility rates, discount). "
        "Prefills from profile + public retrofit cost bands; adjust before capital plan."
    )
    area = float(
        profile.get("conditioned_floor_area_ft2")
        or profile.get("floor_area_ft2")
        or 50000.0
    )
    rates = profile.get("utility") or {}
    from wattlab.finance import (
        DEFAULT_DISCOUNT_RATE,
        DEFAULT_ESCALATION_RATE,
        DEFAULT_MEASURE_LIFE_YEARS,
    )

    # Prefill $/ft2 from controls_first / major_hvac_renewal bands
    cost_usd_per_ft2_default = 3.0
    try:
        from wattlab.benchmarks.costs import load_registry

        bands = {r["scope"]: r for r in load_registry()}
        if "controls_first" in bands:
            cost_usd_per_ft2_default = float(bands["controls_first"].get("p50") or 3.0)
    except Exception:
        pass

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
            "Capital $/ft² (optional rollup)",
            min_value=0.0,
            max_value=100.0,
            value=float(cost_usd_per_ft2_default),
            step=0.25,
            key="ecm_roi_usd_ft2",
            help="Screening band for package capital when measure costs are blank.",
        )
    st.caption(f"Floor area for $/ft² math: {area:,.0f} ft² → package capital ≈ ${usd_per_ft2 * area:,.0f}")

    st.divider()
    st.subheader("Capital plan + guardrails")
    if not measures:
        st.info("Build measures above to roll up capital plan.")
        return

    econ_rows = []
    for mid in measures:
        p = proxies.get(mid) or {}
        cost = float(costs.get(mid) or 0.0)
        if cost <= 0:
            # Spread package $/ft2 across selected measures as screening default
            cost = (usd_per_ft2 * area) / max(len(measures), 1)
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

    bench = st.session_state.get("studio_benchmark_summary") or {}
    property_type = str(profile.get("building_type") or profile.get("property_type") or "office")
    site_eui = None
    if isinstance(bench, dict) and bench.get("campus"):
        site_eui = bench["campus"].get("site_eui_kbtu_ft2")
        area = float(bench["campus"].get("floor_area_ft2") or area)
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
        "roi_params": {
            "elec_usd_per_kwh": elec,
            "gas_usd_per_therm": gas,
            "discount_rate": discount,
            "escalation_rate": escalation,
            "life_years": life_years,
            "usd_per_ft2": usd_per_ft2,
            "floor_area_ft2": area,
        },
        "capital_plan_totals": totals,
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
    st.caption("Same Twin deliverable builder — report + workbook + model zip from the latest Studio report.")
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
                meta = package_deliverables(
                    out_dir=dest,
                    scorecard=sc,
                    report=report,
                    profile=profile,
                )
                st.session_state["studio_deliverable"] = meta
                st.success(f"Package → {meta.get('out_dir')}")
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
