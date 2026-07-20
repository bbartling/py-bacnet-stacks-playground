"""Twin / calibrate — profile + Docker sims + modeled vs actual."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from wattlab.config import ARTIFACTS
from wattlab.defaults import resolve_profile
from wattlab.seed import gap_report
from wattlab.studio.workspace import reports_dir, runs_dir


def _bundle() -> Any:
    return st.session_state.get("studio_bundle")


def _profile() -> dict[str, Any] | None:
    return st.session_state.get("studio_profile")


def render() -> None:
    st.header("Twin / calibrate — EnergyPlus vs bills")
    st.caption(
        "Resolve building inputs (data-model driven — no city hardcodes). "
        "Dry-run or Docker EnergyPlus; compare modeled months to actual fuel. "
        "Charts follow EnergyPlusAPIHelper post-sim patterns (OA/zone vibe) without host pyenergyplus."
    )

    bundle = _bundle()
    seed: dict[str, Any] = {}
    if bundle is not None and getattr(bundle, "model_seed", None):
        seed = dict(bundle.model_seed)

    defaults = {
        "building_type": seed.get("building_type") or "",
        "city": seed.get("city") or "",
        "floor_area_ft2": float(seed.get("floor_area_ft2") or 0) or 100000.0,
        "floors": int(seed.get("floors") or 3),
        "lat": seed.get("lat"),
        "lon": seed.get("lon"),
    }
    energy = st.session_state.get("studio_energy")
    campus = st.session_state.get("studio_campus")
    if campus is not None:
        if defaults["lat"] is None and campus.lat is not None:
            defaults["lat"] = campus.lat
        if defaults["lon"] is None and campus.lon is not None:
            defaults["lon"] = campus.lon
        if campus.buildings:
            defaults["floor_area_ft2"] = float(campus.buildings[0].floor_area_ft2)
            defaults["building_type"] = defaults["building_type"] or campus.buildings[0].property_type

    with st.form("twin_profile_form"):
        c1, c2, c3 = st.columns(3)
        btype = c1.text_input("building_type", value=str(defaults["building_type"] or ""), key="twin_btype")
        city = c2.text_input("city", value=str(defaults["city"] or ""), key="twin_city")
        area = c3.number_input("floor_area_ft2", value=float(defaults["floor_area_ft2"]), min_value=1.0, key="twin_area")
        c4, c5, c6 = st.columns(3)
        floors = c4.number_input("floors", value=int(defaults["floors"]), min_value=1, key="twin_floors")
        lat = c5.text_input("lat", value="" if defaults["lat"] is None else str(defaults["lat"]), key="twin_lat")
        lon = c6.text_input("lon", value="" if defaults["lon"] is None else str(defaults["lon"]), key="twin_lon")
        measure_set = st.selectbox("measure_set", ["good", "better", "best"], index=2, key="twin_mset")
        submitted = st.form_submit_button("Resolve profile")

    if submitted:
        if not btype.strip() or not city.strip():
            st.error("building_type and city are required (NEEDS_INPUT — do not invent).")
        else:
            minimal: dict[str, Any] = {
                "building_type": btype.strip(),
                "city": city.strip(),
                "floor_area_ft2": float(area),
                "floors": int(floors),
                "measure_set": measure_set,
            }
            if lat.strip():
                minimal["lat"] = float(lat)
            if lon.strip():
                minimal["lon"] = float(lon)
            profile = resolve_profile(minimal)
            st.session_state["studio_profile"] = profile
            st.session_state["studio_measure_set"] = measure_set
            st.success("Profile resolved.")

    if bundle is not None:
        gaps = gap_report(bundle)
        missing = [g for g in gaps if g.get("severity") == "required" and g.get("status") == "missing"]
        if missing:
            st.warning("Dump still missing: " + ", ".join(g["field"] for g in missing))

    profile = _profile()
    if not profile:
        st.info("Resolve a profile above (or have Codex write answers.json → wattlab twin).")
        return

    with st.expander("Resolved profile", expanded=False):
        st.json(profile)

    measure_set = st.session_state.get("studio_measure_set") or profile.get("measure_set") or "best"
    proxies = st.session_state.get("studio_proxies") or {}
    run_profile = dict(profile)
    run_profile["measure_set"] = measure_set
    if proxies:
        run_profile["proxy_savings"] = proxies

    d1, d2 = st.columns(2)
    if d1.button("Dry-run plan (no Docker)", key="twin_dry_run"):
        from wattlab.easy_button import run_easy_button

        plan = run_easy_button(profile=run_profile, dry_run=True, measure_set=measure_set)
        st.session_state["studio_plan"] = plan
        out = reports_dir() / "last_dry_run_plan.json"
        out.write_text(json.dumps(plan, indent=2), encoding="utf-8")
        st.success(f"Dry-run plan → {out}")

    if d2.button("Run EnergyPlus (Docker)", key="twin_real_run"):
        from wattlab.easy_button import run_easy_button

        with st.spinner("Running EnergyPlus via Docker…"):
            try:
                report = run_easy_button(profile=run_profile, measure_set=measure_set)
                st.session_state["studio_report"] = report
                rid = report.get("run_id") or "run"
                dest = runs_dir() / str(rid)
                dest.mkdir(parents=True, exist_ok=True)
                (dest / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                st.success(f"Run complete: {rid}")
            except Exception as exc:
                st.error(f"EnergyPlus run failed (is Docker up?): {exc}")

    plan = st.session_state.get("studio_plan")
    if plan:
        st.subheader("Plan")
        steps = pd.DataFrame(plan.get("steps") or [])
        if not steps.empty:
            st.dataframe(steps, width="stretch", hide_index=True)

    report = st.session_state.get("studio_report")
    if report:
        st.subheader("Results vs ESCO proxies")
        savings = report.get("savings_by_measure") or []
        if savings:
            st.dataframe(pd.json_normalize(savings), width="stretch", hide_index=True)
        cross = report.get("crosscheck")
        if cross:
            st.subheader(f"Crosscheck: {cross.get('overall_verdict')}")
            mrows = cross.get("measures") or []
            if mrows:
                dfm = pd.DataFrame(mrows)
                st.dataframe(dfm, width="stretch", hide_index=True)
                if {"ep_savings_kwh", "proxy_savings_kwh"}.issubset(dfm.columns):
                    st.bar_chart(dfm.set_index("measure_id")[["ep_savings_kwh", "proxy_savings_kwh"]])
            if cross.get("g14"):
                st.json(cross["g14"], expanded=False)

    # Modeled vs bills (from dump or scorecard)
    st.subheader("Modeled vs actual fuel")
    scorecard_path = st.text_input(
        "calibration_scorecard.json (optional)",
        key="twin_scorecard",
        placeholder=str(ARTIFACTS / "…/calibration_scorecard.json"),
    )
    monthly_model: list[dict[str, Any]] = []
    bills_rows: list[dict[str, Any]] = []
    if scorecard_path.strip():
        sp = Path(scorecard_path.strip())
        if sp.is_file():
            sc = json.loads(sp.read_text(encoding="utf-8"))
            monthly_model = list((sc.get("annual") or {}).get("monthly") or [])
            for pm in (sc.get("utility_bills") or {}).get("per_month") or []:
                bills_rows.append({
                    "month": pm.get("month"),
                    "observed_kwh": pm.get("observed_kwh"),
                    "modeled_kwh": pm.get("modeled_kwh"),
                    "delta_kwh": pm.get("delta_kwh"),
                })
            st.caption(f"Scorecard status: {sc.get('status') or sc.get('overall')}")
    if bundle is not None and not getattr(bundle, "utility_bills", pd.DataFrame()).empty:
        ub = bundle.utility_bills
        st.dataframe(ub.head(24), width="stretch", hide_index=True)

    if bills_rows:
        bdf = pd.DataFrame(bills_rows)
        st.dataframe(bdf, width="stretch", hide_index=True)
        if "observed_kwh" in bdf.columns and "modeled_kwh" in bdf.columns:
            st.line_chart(bdf.set_index("month")[["observed_kwh", "modeled_kwh"]])
    elif monthly_model:
        st.dataframe(pd.DataFrame(monthly_model).head(24), width="stretch", hide_index=True)

    st.subheader("Iteration history")
    manifests = sorted(ARTIFACTS.glob("wattlab_*/run_manifest.json"), reverse=True)[:10]
    if not manifests:
        st.caption("No prior runs in .artifacts/")
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
        st.dataframe(pd.DataFrame(hist), width="stretch", hide_index=True)
