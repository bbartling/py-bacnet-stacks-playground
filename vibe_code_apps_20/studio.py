"""WattLab Studio — the ESCO / capital-planning cockpit for the human + AI agent.

Launch with ``wattlab studio`` (or ``streamlit run studio.py``). Fully
functional in dry-run without Docker: ingest a vibe19 WattLab dump, resolve a
building profile with responsive defaults, pick measures (catalog +
FDD-suggested), price them with the ESCO bin-method proxies, plan/run the
EnergyPlus twin loop with crosscheck verdicts, and roll up the capital plan.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from wattlab.config import ARTIFACTS
from wattlab.defaults import resolve_profile
from wattlab.finance import capital_plan, measure_economics, plan_to_csv
from wattlab.measures.measure_sets import expand_measure_set, list_measure_sets
from wattlab.seed import gap_report, load_bundle

st.set_page_config(page_title="WattLab Studio", page_icon="⚡", layout="wide")

PAGES = ["Ingest", "Model", "Benchmark", "Measures", "Twin loop", "Capital plan"]

LIBERTY_CAMPUS = Path(__file__).resolve().parent / "examples" / "liberty" / "campus.json"

# Screening assumptions for ESCO proxy savings when the dump lacks specifics.
PROXY_ASSUMPTIONS = {
    "supply_cfm_per_ft2": 1.0,
    "oa_fraction": 0.20,
    "fan_w_per_cfm": 0.8,
    "kw_per_ton": 0.9,
    "existing_schedule": {"shifts": [8, 8, 8], "days_per_week": 7},
    "proposed_schedule": {"shifts": [1, 8, 3], "days_per_week": 5, "override_allowance": 0.10},
}

DEFAULT_MEASURE_COSTS = {
    "ECM-AHU-SCHED-ALIGN": 8000.0,
    "ECM-CHILLER-LOCKOUT": 6000.0,
    "ECM-SAT-RESET": 12000.0,
    "ECM-GL36-AIRSIDE": 45000.0,
}


def _state(key: str, default: Any = None) -> Any:
    return st.session_state.get(key, default)


# ---------------------------------------------------------------------------
# ESCO proxy savings per measure (screening-grade, weather-bin driven)
# ---------------------------------------------------------------------------

def estimate_proxy_savings(profile: dict[str, Any], measure_ids: list[str]) -> dict[str, dict[str, float]]:
    """Screening proxy savings per measure from the ESCO bin calculators."""
    from wattlab.bench.registry import get
    from wattlab.bench import runner  # noqa: F401  (registers calculators)
    from wattlab.weather.bins import washington_dc_noaa

    area = float(
        profile.get("conditioned_floor_area_ft2")
        or profile.get("floor_area_ft2")
        or 50000.0
    )
    supply_cfm = area * PROXY_ASSUMPTIONS["supply_cfm_per_ft2"]
    oa_cfm = supply_cfm * PROXY_ASSUMPTIONS["oa_fraction"]
    fan_kw = supply_cfm * PROXY_ASSUMPTIONS["fan_w_per_cfm"] / 1000.0
    kw_per_ton = PROXY_ASSUMPTIONS["kw_per_ton"]
    bins = washington_dc_noaa()
    existing = PROXY_ASSUMPTIONS["existing_schedule"]
    proposed = PROXY_ASSUMPTIONS["proposed_schedule"]

    out: dict[str, dict[str, float]] = {}
    for mid in measure_ids:
        try:
            if "SCHED" in mid:
                fan = get("scheduling_fan_bins")({
                    "fan_kw_total": fan_kw,
                    "existing_schedule": existing,
                    "proposed_schedule": proposed,
                    "bins": bins,
                })
                cool = get("scheduling_cooling_bins")({
                    "oa_cfm_total": oa_cfm,
                    "kw_per_ton": kw_per_ton,
                    "existing_schedule": existing,
                    "proposed_schedule": proposed,
                    "bins": bins,
                })
                heat = get("scheduling_heating_bins")({
                    "oa_cfm_total": oa_cfm,
                    "existing_schedule": existing,
                    "proposed_schedule": proposed,
                    "bins": bins,
                })
                out[mid] = {
                    "savings_kwh": round(fan["savings_kwh"] + cool["savings_kwh"], 1),
                    "savings_therms": round(heat["savings_therms"], 1),
                }
            elif "GL36" in mid or "STATIC" in mid:
                res = get("static_pressure_reset")({
                    "pressure_ratio": 0.7,
                    "units": [{
                        "tag": "supply fans",
                        "motor_kw": fan_kw,
                        "avg_speed_fraction": 0.75,
                        "annual_hours": 3289.0,
                    }],
                })
                out[mid] = {"savings_kwh": round(res["savings_kwh"], 1), "savings_therms": 0.0}
            elif "LOCKOUT" in mid or "ECON" in mid:
                res = get("dewpoint_economizer")({
                    "unit_cfm_total": supply_cfm,
                    "oa_cfm_total": oa_cfm,
                    "return_enthalpy": 28.3,
                    "discharge_enthalpy": 24.5,
                    "kw_per_ton": kw_per_ton,
                    "unit_type": "cv",
                    "schedule": existing,
                    "bins": bins,
                })
                out[mid] = {"savings_kwh": round(res["savings_kwh"], 1), "savings_therms": 0.0}
            elif "SAT" in mid or "DAT" in mid:
                res = get("dat_reset_bins")({
                    "total_cfm": supply_cfm,
                    "oa_cfm": oa_cfm,
                    "return_enthalpy": 28.3,
                    "supply_enthalpy": 23.2,
                    "kw_per_ton": kw_per_ton,
                    "schedule": existing,
                    "bins": bins,
                    "reset": [
                        {"temp": t, "proposed_supply_enthalpy": h, "vav_fraction": v}
                        for t, h, v in [
                            (92, 23.63, 0.925), (87, 24.03, 0.8), (82, 24.5, 0.7),
                            (77, 25.0, 0.7), (72, 25.5, 0.7), (67, 26.0, 0.7),
                        ]
                    ],
                })
                out[mid] = {"savings_kwh": round(res["savings_kwh"], 1), "savings_therms": 0.0}
            else:
                out[mid] = {"savings_kwh": 0.0, "savings_therms": 0.0}
        except Exception:
            out[mid] = {"savings_kwh": 0.0, "savings_therms": 0.0}
    return out


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

def page_ingest() -> None:
    st.header("Ingest — vibe19 WattLab dump")
    st.caption(
        "Upload the zip from vibe19's Export tab (**Build WattLab dump (zip)**) "
        "or point at an extracted folder."
    )
    up = st.file_uploader("WattLab dump zip", type=["zip"], key="studio_dump_upload")
    folder = st.text_input("…or path to an extracted dump folder", key="studio_dump_folder")
    if st.button("Load dump", key="studio_load_dump"):
        try:
            if up is not None:
                tmp = Path(tempfile.mkdtemp(prefix="studio_dump_")) / "dump.zip"
                tmp.write_bytes(up.getvalue())
                bundle = load_bundle(tmp)
            elif folder.strip():
                bundle = load_bundle(folder.strip())
            else:
                st.warning("Upload a zip or enter a folder path first.")
                return
            st.session_state["studio_bundle"] = bundle
            st.success(f"Loaded dump for building: {bundle.building_id}")
        except Exception as exc:
            st.error(f"Could not load dump: {exc}")

    bundle = _state("studio_bundle")
    if bundle is None:
        st.info("No dump loaded yet. The Model page still works with manual inputs + defaults.")
        return

    summary = bundle.summary()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Building", str(summary.get("building_id") or "?"))
    c2.metric("Tables", str(len(summary.get("tables") or {})))
    c3.metric("Utility bills", "yes" if summary.get("has_bills") else "no")
    c4.metric("Observed weather", "yes" if summary.get("has_observed_weather") else "no")

    st.subheader("Gap checklist — what the human still provides")
    gaps = pd.DataFrame(gap_report(bundle))
    st.dataframe(gaps, width='stretch', hide_index=True)

    if not bundle.fdd_summary.empty:
        st.subheader("Fault highlights")
        st.dataframe(bundle.fdd_summary.head(25), width='stretch', hide_index=True)
    if bundle.schedule_inference:
        st.subheader("Inferred schedules")
        st.json(bundle.schedule_inference, expanded=False)


def page_model() -> None:
    st.header("Model — building profile with responsive defaults")
    bundle = _state("studio_bundle")
    seed = (bundle.model_seed if bundle else {}) or {}

    with st.form("studio_profile_form"):
        c1, c2, c3 = st.columns(3)
        btype = c1.text_input("Building type", value=str(seed.get("building_type") or "office"), key="studio_btype")
        city = c2.text_input("City", value=str(seed.get("city") or "madison"), key="studio_city")
        area = c3.number_input(
            "Floor area (ft²)", min_value=1000.0, max_value=2_000_000.0,
            value=float(seed.get("floor_area_ft2") or 50000.0), step=1000.0, key="studio_area",
        )
        c4, c5, c6 = st.columns(3)
        floors = c4.number_input("Floors", min_value=1, max_value=60, value=int(seed.get("floors") or 1), key="studio_floors")
        elec = c5.number_input("Electric $/kWh", min_value=0.01, max_value=1.0, value=0.12, step=0.01, key="studio_elec_rate")
        gas = c6.number_input("Gas $/therm", min_value=0.05, max_value=5.0, value=0.80, step=0.05, key="studio_gas_rate")
        submitted = st.form_submit_button("Resolve profile with defaults")

    if submitted:
        minimal = {
            "building_type": btype,
            "city": city,
            "floor_area_ft2": area,
            "floors": int(floors),
            "utility": {"elec_usd_per_kwh": elec, "gas_usd_per_therm": gas},
        }
        profile = resolve_profile(minimal)
        st.session_state["studio_profile"] = profile
        st.success("Profile resolved.")

    profile = _state("studio_profile")
    if not profile:
        st.info("Fill the form and resolve to build the profile.")
        return

    st.subheader("Provenance")
    fs = profile.get("field_sources") or {}
    prov_rows = [
        {"field": k, "value": json.dumps(v.get("value"))[:60] if isinstance(v, dict) else str(v)[:60],
         "source": (v or {}).get("source") if isinstance(v, dict) else "?"}
        for k, v in fs.items()
    ]
    if prov_rows:
        st.dataframe(pd.DataFrame(prov_rows), width='stretch', hide_index=True)

    st.subheader("Calibration status")
    if bundle is not None and bundle.has_bills:
        st.success(
            f"{len(bundle.utility_bills)} months of bills present — the twin loop can gate "
            "against ASHRAE G14 (monthly NMBE ±5%, CV(RMSE) ≤15%)."
        )
    else:
        st.warning("No utility bills yet — savings stay screening-grade until bills are added (Ingest page).")
    with st.expander("Resolved profile JSON"):
        st.json(profile, expanded=False)


def page_benchmark() -> None:
    st.header("Benchmark & Validation — bills before models")
    st.caption(
        "Whole-building sanity screen: annualize utility bills, split shared meters "
        "(as scenarios, not truth), and compare site EUI to peer-group bands "
        "before any EnergyPlus run or ROI is trusted."
    )
    import plotly.express as px
    import plotly.graph_objects as go

    from wattlab.benchmarks import Campus, allocation_scenarios, annual_summary, compare_eui
    from wattlab.benchmarks.meters import ALLOCATION_METHODS

    default_path = str(LIBERTY_CAMPUS) if LIBERTY_CAMPUS.is_file() else ""
    path = st.text_input(
        "campus.json (buildings, meters, bill CSVs)",
        value=str(_state("studio_campus_path", default_path)),
        key="studio_campus_path_input",
        help="See examples/liberty/campus.json for the shared-electric + per-building-gas pattern.",
    )
    if st.button("Load campus bills", key="studio_load_campus"):
        try:
            campus = Campus.from_json(path.strip())
            st.session_state["studio_campus"] = campus
            st.session_state["studio_campus_path"] = path.strip()
            st.success(f"Loaded {campus.label}: {len(campus.buildings)} buildings, {len(campus.meters)} meters.")
        except Exception as exc:
            st.error(f"Could not load campus: {exc}")

    campus = _state("studio_campus")
    if campus is None:
        st.info("Load a campus.json to benchmark. The Liberty example ships with the repo.")
        return

    shared = [m.meter_id for m in campus.meters if m.shared]
    if shared:
        st.caption(
            f"Shared meter(s): {', '.join(shared)} — the split below is a **scenario**, "
            "not truth, until submetering or BAS-derived allocation evidence exists."
        )
    alloc = st.selectbox(
        "Shared-meter allocation", list(ALLOCATION_METHODS[:3]),
        format_func=lambda m: {"area_weighted": "Area-weighted", "equal": "Equal 50/50",
                               "gas_share": "Gas-share proxy"}.get(m, m),
        key="studio_allocation",
    )

    try:
        summary = annual_summary(campus, allocation=alloc)
    except ValueError as exc:
        st.error(f"Could not annualize: {exc}")
        return
    st.session_state["studio_benchmark_summary"] = summary

    w = summary["window"]
    st.subheader(f"Annual window {w['start']} → {w['end']}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Campus site EUI", f"{summary['campus']['site_eui_kbtu_ft2']} kBtu/ft²")
    c2.metric("Electric", f"{summary['campus']['kwh']:,.0f} kWh")
    c3.metric("Gas", f"{summary['campus']['mcf']:,.0f} Mcf")
    c4.metric("Utility cost", f"${summary['campus']['cost_usd']:,.0f}")

    # Per-building EUI vs peer band
    rows = []
    for b in summary["buildings"]:
        cmp = compare_eui(b["site_eui_kbtu_ft2"], b["property_type"])
        rows.append({**b, **{f"peer_{k}": cmp[k] for k in ("p20", "p50", "p80", "band", "vs_median_pct")}})
    dfb = pd.DataFrame(rows)
    st.dataframe(
        dfb[["label", "floor_area_ft2", "kwh", "mcf", "elec_kbtu_ft2", "gas_kbtu_ft2",
             "site_eui_kbtu_ft2", "peer_p50", "peer_band", "peer_vs_median_pct"]],
        width='stretch', hide_index=True,
    )

    fig = go.Figure()
    fig.add_bar(x=dfb["label"], y=dfb["site_eui_kbtu_ft2"], name="Site EUI",
                marker_color=["#d62728" if b == "above_p80" else "#2ca02c" if b == "within_band" else "#ff7f0e"
                              for b in dfb["peer_band"]])
    fig.add_hline(y=float(dfb["peer_p50"].iloc[0]), line_dash="dash", annotation_text="peer median")
    fig.add_hline(y=float(dfb["peer_p80"].iloc[0]), line_dash="dot", annotation_text="peer p80")
    fig.update_layout(height=360, yaxis_title="kBtu/ft²-yr", margin=dict(t=30, b=10))
    st.plotly_chart(fig, width='stretch', key="studio_bm_eui_chart")

    # Allocation scenarios side-by-side
    scen = pd.DataFrame(allocation_scenarios(campus))
    if not scen.empty and shared:
        st.subheader("Allocation scenarios (shared electric)")
        fig2 = px.bar(scen, x="building_id", y="site_eui_kbtu_ft2", color="allocation", barmode="group")
        fig2.update_layout(height=340, yaxis_title="kBtu/ft²-yr", margin=dict(t=30, b=10))
        st.plotly_chart(fig2, width='stretch', key="studio_bm_alloc_chart")

    # Monthly fuel signatures
    st.subheader("Monthly signatures")
    monthly = campus.monthly_frame()
    gas = monthly[monthly["fuel"] == "gas"]
    elec = monthly[monthly["fuel"] == "electricity"]
    t1, t2 = st.tabs(["Gas (heating signature)", "Electric (kWh + demand)"])
    with t1:
        fig3 = px.line(gas, x="month", y="usage", color="meter_id", labels={"usage": "Mcf"})
        fig3.update_layout(height=360, margin=dict(t=30, b=10))
        st.plotly_chart(fig3, width='stretch', key="studio_bm_gas_chart")
        summer = gas[gas["month"].str[5:7].isin(["06", "07", "08"])]
        base = summer.groupby("meter_id")["usage"].mean().round(1)
        if not base.empty:
            st.caption(
                "Average summer-month gas (DHW/reheat baseload signal): "
                + ", ".join(f"{k} = {v} Mcf" for k, v in base.items())
            )
    with t2:
        fig4 = go.Figure()
        for mid, grp in elec.groupby("meter_id"):
            fig4.add_scatter(x=grp["month"], y=grp["usage"], name=f"{mid} kWh", mode="lines")
            if "demand_kw" in grp.columns and grp["demand_kw"].notna().any():
                fig4.add_scatter(x=grp["month"], y=grp["demand_kw"], name=f"{mid} billed kW",
                                 mode="lines", yaxis="y2", line=dict(dash="dot"))
        fig4.update_layout(
            height=360, margin=dict(t=30, b=10), yaxis_title="kWh",
            yaxis2=dict(title="kW", overlaying="y", side="right", showgrid=False),
        )
        st.plotly_chart(fig4, width='stretch', key="studio_bm_elec_chart")


def page_measures() -> None:
    st.header("Measures — catalog + FDD-suggested, priced by ESCO proxies")
    profile = _state("studio_profile") or {}

    sets = list_measure_sets()
    labels = {s["id"]: f"{s['label']} — {', '.join(s['measure_ids'])}" for s in sets}
    choice = st.selectbox(
        "Measure set", options=[s["id"] for s in sets],
        format_func=lambda k: labels.get(k, k), index=len(sets) - 1 if sets else 0,
        key="studio_measure_set",
    )

    bundle = _state("studio_bundle")
    suggested: list[dict[str, Any]] = []
    if bundle is not None and bundle.files:
        try:
            from wattlab.bridge import suggest_from_bundle

            root = next(iter(bundle.files.values())).parent
            suggested = suggest_from_bundle(root).get("measures") or []
        except Exception:
            suggested = []

    if st.button("Build measure list", key="studio_build_measures"):
        measures = expand_measure_set(choice)
        known = {m.get("measure_id") for m in measures}
        for m in suggested:
            if m.get("measure_id") not in known:
                measures.append(m)
        st.session_state["studio_measures"] = measures
        mids = [m["measure_id"] for m in measures]
        st.session_state["studio_proxies"] = estimate_proxy_savings(profile, mids)
        st.success(f"{len(measures)} measures with proxy savings estimated.")

    measures = _state("studio_measures") or []
    proxies = _state("studio_proxies") or {}
    if not measures:
        st.info("Pick a measure set and build the list.")
        return
    if suggested:
        st.caption(f"{len(suggested)} FDD-suggested measure(s) merged from the vibe19 bridge.")

    rows = []
    saved_costs = _state("studio_costs") or {}
    for m in measures:
        mid = m["measure_id"]
        px = proxies.get(mid) or {}
        rows.append({
            "measure_id": mid,
            "title": m.get("title") or mid,
            "source": m.get("source") or "catalog",
            "proxy_savings_kwh": px.get("savings_kwh", 0.0),
            "proxy_savings_therms": px.get("savings_therms", 0.0),
            "cost_usd": saved_costs.get(mid, DEFAULT_MEASURE_COSTS.get(mid, 10000.0)),
        })
    edited = st.data_editor(
        pd.DataFrame(rows),
        width='stretch',
        hide_index=True,
        disabled=["measure_id", "title", "source"],
        key="studio_measure_editor",
    )
    st.session_state["studio_costs"] = {
        r["measure_id"]: float(r["cost_usd"]) for _, r in edited.iterrows()
    }
    st.session_state["studio_proxies"] = {
        r["measure_id"]: {
            "savings_kwh": float(r["proxy_savings_kwh"]),
            "savings_therms": float(r["proxy_savings_therms"]),
        }
        for _, r in edited.iterrows()
    }


def page_twin_loop() -> None:
    st.header("Twin loop — EnergyPlus baseline + progressive measures")
    profile = _state("studio_profile")
    if not profile:
        st.info("Resolve a profile on the Model page first.")
        return
    measure_set = _state("studio_measure_set") or "best"
    proxies = _state("studio_proxies") or {}
    run_profile = dict(profile)
    run_profile["measure_set"] = measure_set
    if proxies:
        run_profile["proxy_savings"] = proxies

    c1, c2 = st.columns(2)
    if c1.button("Dry-run plan (no Docker)", key="studio_dry_run"):
        from wattlab.easy_button import run_easy_button

        plan = run_easy_button(profile=run_profile, dry_run=True, measure_set=measure_set)
        st.session_state["studio_plan"] = plan
        st.success("Dry-run plan built.")
    if c2.button("Run EnergyPlus (Docker)", key="studio_real_run"):
        from wattlab.easy_button import run_easy_button

        with st.spinner("Running EnergyPlus via Docker…"):
            try:
                report = run_easy_button(profile=run_profile, measure_set=measure_set)
                st.session_state["studio_report"] = report
                st.success(f"Run complete: {report.get('run_id')}")
            except Exception as exc:
                st.error(f"EnergyPlus run failed (is Docker up?): {exc}")

    plan = _state("studio_plan")
    if plan:
        st.subheader("Plan")
        steps = pd.DataFrame(plan.get("steps") or [])
        if not steps.empty:
            st.dataframe(steps, width='stretch', hide_index=True)
        st.caption(f"Approved measures: {', '.join(plan.get('approved_measure_ids') or [])}")

    report = _state("studio_report")
    if report:
        st.subheader("Results")
        savings = report.get("savings_by_measure") or []
        if savings:
            st.dataframe(pd.json_normalize(savings), width='stretch', hide_index=True)
        cross = report.get("crosscheck")
        if cross:
            st.subheader(f"Crosscheck verdict: {cross.get('overall_verdict')}")
            mrows = cross.get("measures") or []
            if mrows:
                dfm = pd.DataFrame(mrows)
                st.dataframe(dfm, width='stretch', hide_index=True)
                chart = dfm.set_index("measure_id")[["ep_savings_kwh", "proxy_savings_kwh"]]
                st.bar_chart(chart)
            if cross.get("g14"):
                st.json(cross["g14"], expanded=False)

    st.subheader("Iteration history")
    manifests = sorted(ARTIFACTS.glob("wattlab_*/run_manifest.json"), reverse=True)[:10]
    if not manifests:
        st.caption("No prior runs found in artifacts/.")
    else:
        hist = []
        for mp in manifests:
            try:
                m = json.loads(mp.read_text(encoding="utf-8"))
                hist.append({
                    "run_id": m.get("run_id"),
                    "status": m.get("status"),
                    "started_at": m.get("started_at"),
                    "dir": str(mp.parent),
                })
            except Exception:
                continue
        st.dataframe(pd.DataFrame(hist), width='stretch', hide_index=True)


def page_capital_plan() -> None:
    st.header("Capital plan — payback / ROI / NPV rollup")
    measures = _state("studio_measures") or []
    proxies = _state("studio_proxies") or {}
    costs = _state("studio_costs") or {}
    if not measures:
        st.info("Build a measure list on the Measures page first.")
        return

    c1, c2, c3 = st.columns(3)
    elec = c1.number_input("Electric $/kWh", min_value=0.01, max_value=1.0, value=float(_state("studio_elec_rate", 0.12)), step=0.01, key="studio_cp_elec")
    gas = c2.number_input("Gas $/therm", min_value=0.05, max_value=5.0, value=float(_state("studio_gas_rate", 0.80)), step=0.05, key="studio_cp_gas")
    life = c3.number_input("Measure life (years)", min_value=1, max_value=40, value=15, key="studio_cp_life")

    # Prefer EnergyPlus incremental savings when a run exists; else ESCO proxy.
    report = _state("studio_report") or {}
    ep_by_measure = {
        str(r.get("measure_id")): (r.get("vs_previous") or {})
        for r in report.get("savings_by_measure") or []
    }

    rows = []
    for m in measures:
        mid = m["measure_id"]
        ep = ep_by_measure.get(mid) or {}
        px = proxies.get(mid) or {}
        kwh = ep.get("kwh_saved") if ep.get("kwh_saved") is not None else px.get("savings_kwh", 0.0)
        therms = ep.get("therms_saved") if ep.get("therms_saved") is not None else px.get("savings_therms", 0.0)
        rows.append(measure_economics(
            measure_id=mid,
            title=m.get("title") or mid,
            implementation_cost_usd=float(costs.get(mid, DEFAULT_MEASURE_COSTS.get(mid, 10000.0))),
            kwh_saved=float(kwh or 0.0),
            therms_saved=float(therms or 0.0),
            elec_rate_usd_per_kwh=elec,
            gas_rate_usd_per_therm=gas,
            measure_life_years=int(life),
        ))
    plan = capital_plan(rows)
    st.session_state["studio_capital_plan"] = plan

    # ---- Benchmark guardrail gate (blocks quiet ROI publication) --------
    from wattlab.benchmarks import gate_capital_plan

    bm = _state("studio_benchmark_summary")
    profile = _state("studio_profile") or {}
    if bm and bm.get("buildings"):
        blds = bm["buildings"]
        labels = {b["building_id"]: b["label"] for b in blds}
        pick = st.selectbox(
            "Gate against building (from Benchmark page bills)",
            [b["building_id"] for b in blds],
            format_func=lambda k: labels.get(k, k),
            key="studio_gate_building",
        )
        b = next(x for x in blds if x["building_id"] == pick)
        gate = gate_capital_plan(
            plan,
            property_type=b["property_type"],
            floor_area_ft2=float(b["floor_area_ft2"]),
            baseline_kwh=float(b["kwh"]),
            baseline_therms=float(b["therms"]),
            site_eui_kbtu_ft2=float(b["site_eui_kbtu_ft2"]),
        )
    else:
        area = float(profile.get("conditioned_floor_area_ft2") or profile.get("floor_area_ft2") or 0.0)
        gate = gate_capital_plan(
            plan,
            property_type=str(profile.get("building_type") or "office"),
            floor_area_ft2=area,
        )
    st.session_state["studio_guardrail_gate"] = gate

    if gate["verdict"] == "INVESTIGATE":
        st.error(
            f"Benchmark gate: INVESTIGATE — {gate['investigate_count']} check(s) outside the "
            "benchmark envelope. Review below before publishing this ROI."
        )
    else:
        st.success("Benchmark gate: PUBLISH — plan is inside the benchmark envelope.")
    with st.expander("Guardrail checks", expanded=gate["verdict"] == "INVESTIGATE"):
        st.dataframe(
            pd.DataFrame([
                {"check": c["check"], "status": c["status"], "detail": c["detail"]}
                for c in gate["checks"]
            ]),
            width='stretch', hide_index=True,
        )

    totals = plan["totals"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total cost", f"${totals['implementation_cost_usd']:,.0f}")
    c2.metric("Annual savings", f"${totals['annual_cost_saved_usd']:,.0f}")
    pb = totals.get("blended_simple_payback_years")
    c3.metric("Blended payback", f"{pb:.1f} yr" if pb is not None else "—")
    c4.metric("Portfolio NPV", f"${totals['npv_usd']:,.0f}")

    source = "EnergyPlus (vs previous step)" if ep_by_measure else "ESCO bin-method proxies"
    st.caption(f"Savings source: {source}.")
    st.dataframe(
        pd.DataFrame(plan["measures"]).drop(columns=["assumptions"], errors="ignore"),
        width='stretch',
        hide_index=True,
    )
    d1, d2 = st.columns(2)
    d1.download_button(
        "Download capital plan CSV", data=plan_to_csv(plan),
        file_name="wattlab_capital_plan.csv", mime="text/csv", key="studio_dl_csv",
    )
    d2.download_button(
        "Download capital plan JSON", data=json.dumps(plan, indent=2),
        file_name="wattlab_capital_plan.json", mime="application/json", key="studio_dl_json",
    )


def main() -> None:
    st.sidebar.title("WattLab Studio")
    st.sidebar.caption(
        "vibe19 dump → digital twin → ESCO capital plan. "
        "The agent iterates EnergyPlus; the ESCO bin calculators referee."
    )
    page = st.sidebar.radio("Workflow", PAGES, key="studio_page")
    if page == "Ingest":
        page_ingest()
    elif page == "Model":
        page_model()
    elif page == "Benchmark":
        page_benchmark()
    elif page == "Measures":
        page_measures()
    elif page == "Twin loop":
        page_twin_loop()
    else:
        page_capital_plan()


main()
