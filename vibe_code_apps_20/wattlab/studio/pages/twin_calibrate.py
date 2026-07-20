"""Twin / calibrate — profile + Docker sims + 08-style iteration viewer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from wattlab.config import ARTIFACTS, ROOT
from wattlab.defaults import resolve_profile
from wattlab.energyplus.timeseries import find_eplusout_csv, load_sim_timeseries
from wattlab.seed import gap_report
from wattlab.studio.ep_viz import (
    floor_plan_figure,
    install_demo_replay,
    list_iteration_runs,
    outdoor_figure,
    publish_run_for_studio,
    read_run_progress,
    zone_mean_by_role,
)
from wattlab.studio.workspace import reports_dir, runs_dir


def _bundle() -> Any:
    return st.session_state.get("studio_bundle")


def _profile() -> dict[str, Any] | None:
    return st.session_state.get("studio_profile")


def _fixture_eplusout() -> Path | None:
    cand = ROOT / "tests" / "fixtures" / "eplusout" / "eplusout.csv"
    return cand if cand.is_file() else None


def _resolve_active_run() -> Path | None:
    """Prefer session selection, then CURRENT_RUN.txt, then latest runs/ entry."""
    active = st.session_state.get("studio_active_run")
    if active and Path(active).is_dir():
        return Path(active)
    pointer = runs_dir() / "CURRENT_RUN.txt"
    if pointer.is_file():
        try:
            p = Path(pointer.read_text(encoding="utf-8").strip())
            if p.is_dir():
                return p
        except OSError:
            pass
    hist = list_iteration_runs(runs_dir(), limit=1)
    if hist and hist[0].get("dir"):
        return Path(str(hist[0]["dir"]))
    return None


def _render_08_panes(run_dir: Path) -> None:
    st.subheader("EnergyPlus visualizer (APIHelper 08 — browser)")
    st.caption(
        "Populated by any AI agent (or Studio buttons) writing `runs/<id>/` "
        "with eplusout.csv. Human: use **Refresh agent runs** after each iteration."
    )
    info = read_run_progress(run_dir)
    if info.get("replay"):
        st.info("Demo replay — fixture eplusout.csv (no live Docker EnergyPlus run).")

    left, right = st.columns([2, 3])
    with left:
        st.markdown("**Manage simulation**")
        st.progress(min(100, max(0, int(info.get("progress") or 0))) / 100.0)
        st.caption(f"status={info.get('status')} · run_id={info.get('run_id')}")
        log = info.get("log_tail") or "(no eplusout.err / console log yet)"
        st.text_area("EnergyPlus output", value=log, height=220, key=f"twin_ep_log_{run_dir.name}")
    with right:
        ts = load_sim_timeseries(run_dir)
        if ts is None:
            nested = find_eplusout_csv(run_dir)
            ts = load_sim_timeseries(nested.parent) if nested else None
        if ts is not None and not ts.outdoor.empty:
            st.plotly_chart(outdoor_figure(ts.outdoor), width="stretch", key=f"twin_oa_{run_dir.name}")
        else:
            st.caption("No outdoor timeseries yet (need eplusout.csv in this run folder).")

    ts2 = load_sim_timeseries(run_dir)
    if ts2 is None:
        nested = find_eplusout_csv(run_dir)
        if nested:
            ts2 = load_sim_timeseries(nested.parent)
    if ts2 is not None:
        roles = zone_mean_by_role(ts2)
        if roles:
            st.plotly_chart(
                floor_plan_figure(roles),
                width="stretch",
                key=f"twin_floor_{run_dir.name}",
            )
        means = ts2.zone_mean_temps()
        if not means.empty:
            st.dataframe(means, width="stretch", hide_index=True)


def render() -> None:
    st.header("Twin / calibrate — EnergyPlus vs bills")
    st.caption(
        "Resolve building inputs from the dump / campus data model (no city hardcodes). "
        "Dry-run or Docker EnergyPlus; AI agents outside Streamlit publish iterations to "
        "`runs/` so this browser page shows APIHelper-08 progress, OA, and floor-plan panes."
    )

    if st.button("Refresh agent runs", key="twin_refresh_runs"):
        active = _resolve_active_run()
        if active is not None:
            st.session_state["studio_active_run"] = str(active)
        st.rerun()

    bundle = _bundle()
    seed: dict[str, Any] = {}
    if bundle is not None and getattr(bundle, "model_seed", None):
        seed = dict(bundle.model_seed)

    defaults = {
        "building_type": seed.get("building_type") or "",
        "city": seed.get("city") or "",
        "floor_area_ft2": float(seed.get("floor_area_ft2") or 0) or 1.0,
        "floors": int(seed.get("floors") or 1),
        "lat": seed.get("lat"),
        "lon": seed.get("lon"),
    }
    campus = st.session_state.get("studio_campus")
    if campus is not None:
        if defaults["lat"] is None and campus.lat is not None:
            defaults["lat"] = campus.lat
        if defaults["lon"] is None and campus.lon is not None:
            defaults["lon"] = campus.lon
        if campus.buildings:
            defaults["floor_area_ft2"] = float(campus.buildings[0].floor_area_ft2) or defaults["floor_area_ft2"]
            defaults["building_type"] = defaults["building_type"] or campus.buildings[0].property_type

    with st.form("twin_profile_form"):
        c1, c2, c3 = st.columns(3)
        btype = c1.text_input("building_type", value=str(defaults["building_type"] or ""), key="twin_btype")
        city = c2.text_input("city", value=str(defaults["city"] or ""), key="twin_city")
        area = c3.number_input(
            "floor_area_ft2",
            value=float(defaults["floor_area_ft2"]),
            min_value=1.0,
            key="twin_area",
        )
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
        st.info(
            "Resolve a profile above (or have an AI agent write answers.json → wattlab twin). "
            "Agent prompt: vibe20_agent_spec/AGENT_TESTER_PROMPT.md"
        )
        # Still show any published 08 panes so agent work is visible before profile
        active_early = _resolve_active_run()
        if active_early is not None:
            _render_08_panes(active_early)
        return

    with st.expander("Resolved profile", expanded=False):
        st.json(profile)

    measure_set = st.session_state.get("studio_measure_set") or profile.get("measure_set") or "best"
    proxies = st.session_state.get("studio_proxies") or {}
    run_profile = dict(profile)
    run_profile["measure_set"] = measure_set
    if proxies:
        run_profile["proxy_savings"] = proxies

    try:
        from wattlab.energyplus.docker import docker_info_ok, image_present
        from wattlab.config import DOCKER_IMAGE

        docker_ok = docker_info_ok()
        img_ok = image_present() if docker_ok else False
    except Exception:
        docker_ok, img_ok = False, False
        DOCKER_IMAGE = "energyplus-mcp-dev"

    if not docker_ok or not img_ok:
        st.warning(
            f"ENVIRONMENT: Docker EnergyPlus image `{DOCKER_IMAGE}` not available from this process. "
            "Mount docker.sock when running Studio in a container. Dry-run and demo replay still work; "
            "AI agents can still publish fixture/replay runs into `runs/` for the browser panes."
        )

    d1, d2, d3 = st.columns(3)
    if d1.button("Dry-run plan (no Docker)", key="twin_dry_run"):
        from wattlab.easy_button import run_easy_button

        plan = run_easy_button(profile=run_profile, dry_run=True, measure_set=measure_set)
        st.session_state["studio_plan"] = plan
        out = reports_dir() / "last_dry_run_plan.json"
        out.write_text(json.dumps(plan, indent=2), encoding="utf-8")
        st.success(f"Dry-run plan → {out}")

    if d2.button("Run EnergyPlus (Docker)", key="twin_real_run"):
        from wattlab.easy_button import run_easy_button

        if not img_ok:
            st.error(f"Cannot run: `{DOCKER_IMAGE}` missing. Use dry-run or demo replay.")
        else:
            with st.spinner("Running EnergyPlus via Docker…"):
                try:
                    report = run_easy_button(profile=run_profile, measure_set=measure_set)
                    st.session_state["studio_report"] = report
                    rid = str(report.get("run_id") or "run")
                    art = Path(
                        report.get("studio_run_dir")
                        or report.get("artifacts_dir")
                        or report.get("artifact_dir")
                        or ""
                    )
                    if art.is_dir() and (runs_dir() / rid).is_dir():
                        dest = runs_dir() / rid
                    elif art.is_dir():
                        dest = publish_run_for_studio(art, run_id=rid, report=report)
                    else:
                        dest = publish_run_for_studio(
                            Path(report.get("artifacts_dir") or "."),
                            run_id=rid,
                            report=report,
                        )
                    st.session_state["studio_active_run"] = str(dest)
                    st.success(f"Run published for browser Twin panes → {dest}")
                except Exception as exc:
                    st.error(f"EnergyPlus run failed: {exc}")

    if d3.button("Load demo replay (fixture eplusout)", key="twin_demo_replay"):
        fixture = _fixture_eplusout()
        if fixture is None:
            st.error("Fixture eplusout.csv not found in package tests/fixtures.")
        else:
            dest = runs_dir() / "demo_replay"
            install_demo_replay(dest, fixture)
            st.session_state["studio_active_run"] = str(dest)
            st.success(f"Demo replay ready for browser → {dest}")

    plan = st.session_state.get("studio_plan")
    if plan:
        st.subheader("Plan")
        steps = pd.DataFrame(plan.get("steps") or [])
        if not steps.empty:
            st.dataframe(steps, width="stretch", hide_index=True)

    report = st.session_state.get("studio_report")
    if report:
        st.subheader("Results vs ESCO proxies")
        honesty = report.get("area_honesty")
        scale = report.get("prototype_area_scale")
        if honesty:
            st.warning(honesty)
        if scale:
            st.caption(
                f"prototype_area_scale ≈ {float(scale):.2f}× "
                f"(target {report.get('target_floor_area_ft2')} ft² / "
                f"prototype ~{report.get('prototype_area_ft2_nominal')} ft²)"
            )
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

    active = _resolve_active_run()
    if active is not None:
        st.session_state["studio_active_run"] = str(active)
        _render_08_panes(active)
    else:
        st.info(
            "No published Twin runs yet. An AI agent should write `runs/<id>/eplusout.csv` "
            "(or click demo replay / Docker run). See AGENT_TESTER_PROMPT.md."
        )

    st.subheader("Modeled vs actual fuel")
    ub_path = st.session_state.get("studio_utility_bills_path")
    scorecard_path = st.text_input(
        "calibration_scorecard.json (optional)",
        key="twin_scorecard",
        placeholder=str(ARTIFACTS / "…/calibration_scorecard.json"),
    )
    bills_rows: list[dict[str, Any]] = []
    monthly_model: list[dict[str, Any]] = []
    if scorecard_path.strip():
        sp = Path(scorecard_path.strip())
        if sp.is_file():
            sc = json.loads(sp.read_text(encoding="utf-8"))
            monthly_model = list((sc.get("annual") or {}).get("monthly") or [])
            for pm in (sc.get("utility_bills") or {}).get("per_month") or []:
                bills_rows.append(
                    {
                        "month": pm.get("month"),
                        "observed_kwh": pm.get("observed_kwh"),
                        "modeled_kwh": pm.get("modeled_kwh"),
                        "delta_kwh": pm.get("delta_kwh"),
                    }
                )
            st.caption(f"Scorecard status: {sc.get('status') or sc.get('overall')}")

    if bundle is not None and not getattr(bundle, "utility_bills", pd.DataFrame()).empty:
        ub = bundle.utility_bills
        st.caption("utility_bills from dump / energy bridge")
        st.dataframe(ub.head(24), width="stretch", hide_index=True)
    elif ub_path and Path(ub_path).is_file():
        ub = pd.read_csv(ub_path)
        st.caption(f"utility_bills bridge → {ub_path}")
        st.dataframe(ub.head(24), width="stretch", hide_index=True)

    if bills_rows:
        bdf = pd.DataFrame(bills_rows)
        st.dataframe(bdf, width="stretch", hide_index=True)
        if "observed_kwh" in bdf.columns and "modeled_kwh" in bdf.columns:
            st.line_chart(bdf.set_index("month")[["observed_kwh", "modeled_kwh"]])
    elif monthly_model:
        st.dataframe(pd.DataFrame(monthly_model).head(24), width="stretch", hide_index=True)

    st.subheader("Iteration history (agent + Studio)")
    hist = list_iteration_runs(runs_dir(), limit=15)
    if not hist:
        manifests = sorted(ARTIFACTS.glob("wattlab_*/run_manifest.json"), reverse=True)[:10]
        for mp in manifests:
            try:
                m = json.loads(mp.read_text(encoding="utf-8"))
                hist.append(
                    {
                        "run_id": m.get("run_id"),
                        "status": m.get("status"),
                        "dir": str(mp.parent),
                        "progress": 100 if m.get("status") in {"ok", "success", "SUCCESS"} else 0,
                    }
                )
            except Exception:
                continue
    if not hist:
        st.caption("No prior runs in workspace runs/.")
    else:
        st.dataframe(pd.DataFrame(hist), width="stretch", hide_index=True)
        pick = st.selectbox(
            "Inspect iteration",
            options=[h.get("dir") for h in hist if h.get("dir")],
            key="twin_iter_pick",
        )
        if pick and st.button("Show 08 panes for selection", key="twin_show_iter"):
            st.session_state["studio_active_run"] = pick
            st.rerun()
