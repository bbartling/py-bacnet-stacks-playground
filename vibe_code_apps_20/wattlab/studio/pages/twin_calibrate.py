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
    MULTIFLOOR_HONESTY,
    find_run_idf,
    floor_plan_figure,
    install_demo_replay,
    list_iteration_runs,
    multifloor_office_figure,
    newest_run_with_eplusout,
    outdoor_figure,
    publish_run_for_studio,
    read_run_progress,
    zone_mean_by_role,
)
from wattlab.studio.eui_charts import eui_peer_bullet_figure, month_abbrev
from wattlab.studio.eui_compare import build_eui_index, load_model_eui_from_run
from wattlab.studio.idf_geometry import (
    idf_massing_figure,
    parse_idf_geometry,
    zone_mean_temps_by_name,
)
from wattlab.studio.workspace import reports_dir, runs_dir


def _bundle() -> Any:
    return st.session_state.get("studio_bundle")


def _profile() -> dict[str, Any] | None:
    return st.session_state.get("studio_profile")


def _render_eui_index(
    *,
    profile: dict[str, Any] | None = None,
    run_dir: Path | None = None,
    chart_key: str = "twin_eui_index",
) -> None:
    """Bills vs peer typical EUI vs EnergyPlus model — always visible when data exists."""
    with st.container(border=True):
        st.subheader("EUI index — bills vs peers vs model")
        st.caption(
            "Upright peer band (p20–p80, dashed p50). **Bills** = annualized site EUI from utilities. "
            "**Peers** = public registry for this property type. **Model** = EnergyPlus site intensity "
            "(comparable as EUI; absolute kWh needs site-scale geometry + area_scale=1)."
        )
        bill_eui = None
        ptype = "office"
        bench = st.session_state.get("studio_benchmark_summary") or {}
        if bench.get("campus"):
            bill_eui = bench["campus"].get("site_eui_kbtu_ft2")
        campus = st.session_state.get("studio_campus")
        if campus is not None and campus.buildings:
            ptype = campus.buildings[0].property_type or ptype
            if bill_eui is None:
                try:
                    from wattlab.benchmarks import annual_summary

                    summary = annual_summary(campus)
                    bill_eui = summary["campus"]["site_eui_kbtu_ft2"]
                    st.session_state["studio_benchmark_summary"] = summary
                except Exception:
                    pass
        if profile:
            ptype = profile.get("building_type") or ptype

        model = load_model_eui_from_run(run_dir)
        report = st.session_state.get("studio_report") or {}
        model_eui = model.get("model_eui_kbtu_ft2")
        scale = model.get("prototype_area_scale") or report.get("prototype_area_scale")
        target = model.get("target_floor_area_ft2") or report.get("target_floor_area_ft2")
        if model_eui is None:
            ann = (report.get("baseline_annual") or report.get("annual") or {})
            if ann.get("site_eui_kbtu_ft2_year") is not None:
                model_eui = float(ann["site_eui_kbtu_ft2_year"])
            else:
                for rr in report.get("result_records") or report.get("records") or []:
                    a = (rr or {}).get("annual") or {}
                    if a.get("site_eui_kbtu_ft2_year") is not None:
                        model_eui = float(a["site_eui_kbtu_ft2_year"])
                        break

        if bill_eui is None and model_eui is None:
            st.info(
                "Load Fuel campus bills and/or publish a Twin run with report.json to see "
                "bill EUI vs peer p20/p50/p80 vs model."
            )
            return

        idx = build_eui_index(
            bill_eui_kbtu_ft2=float(bill_eui) if bill_eui is not None else None,
            property_type=str(ptype),
            model_eui_kbtu_ft2=float(model_eui) if model_eui is not None else None,
            prototype_area_scale=float(scale) if scale is not None else None,
            target_floor_area_ft2=float(target) if target is not None else None,
            model_label=str(model.get("run_id") or report.get("run_id") or "EnergyPlus"),
        )
        m1, m2, m3, m4 = st.columns(4)
        m1.metric(
            "Bills site EUI",
            f"{idx['bill_eui_kbtu_ft2']} kBtu/ft²" if idx["bill_eui_kbtu_ft2"] is not None else "—",
            help="Annualized utility bills ÷ floor area (kBtu/ft²·yr).",
        )
        m2.metric(
            "Peer typical (p50)",
            f"{idx['peer_p50']} kBtu/ft²",
            help="Median peer site EUI for this property type (public registry).",
        )
        m3.metric(
            "Model EUI (prototype)",
            f"{idx['model_eui_kbtu_ft2']} kBtu/ft²" if idx["model_eui_kbtu_ft2"] is not None else "—",
            help="EnergyPlus site EUI on prototype area (intensity comparable; scale absolute kWh).",
        )
        m4.metric(
            "Peer band",
            f"p20={idx['peer_p20']} · p80={idx['peer_p80']}",
            help="Peer p20–p80 screening band for this property type.",
        )

        df = pd.DataFrame(idx["rows"])
        st.dataframe(df, width="stretch", hide_index=True)

        series = []
        if idx.get("bill_eui_kbtu_ft2") is not None:
            series.append(
                {
                    "label": "Bills (site)",
                    "eui": float(idx["bill_eui_kbtu_ft2"]),
                    "color": "#1f77b4",
                    "symbol": "diamond",
                }
            )
        if idx.get("model_eui_kbtu_ft2") is not None:
            series.append(
                {
                    "label": "Model (prototype)",
                    "eui": float(idx["model_eui_kbtu_ft2"]),
                    "color": "#d62728",
                    "symbol": "circle",
                }
            )
        fig = eui_peer_bullet_figure(
            peer_p20=float(idx["peer_p20"]),
            peer_p50=float(idx["peer_p50"]),
            peer_p80=float(idx["peer_p80"]),
            series=series,
            title=f"{idx.get('benchmark_name') or idx['property_type']} — bills vs peers vs model",
            height=440,
        )
        st.plotly_chart(fig, width="stretch", key=chart_key)
        if scale and float(scale) > 1.05:
            st.warning(
                f"prototype_area_scale ≈ {float(scale):.2f}× — model intensity (EUI) is comparable; "
                "absolute modeled kWh is NOT site totals until geometry is scaled."
            )
        honesty = model.get("area_honesty") or report.get("area_honesty")
        if honesty:
            st.caption(honesty)


def _fixture_eplusout() -> Path | None:
    cand = ROOT / "tests" / "fixtures" / "eplusout" / "eplusout.csv"
    return cand if cand.is_file() else None


def resolve_active_run_dir(
    runs_root: Path,
    *,
    session_active: str | Path | None = None,
    pinned: bool = False,
) -> Path | None:
    """Resolve Twin's active run.

    Default: ``CURRENT_RUN.txt`` (agent publish pointer), else newest ``runs/``
    by mtime. Sticky ``session_active`` wins only when ``pinned`` (human chose
    Inspect → Show 08 panes).
    """
    if pinned and session_active:
        p = Path(session_active)
        if p.is_dir():
            return p
    pointer = Path(runs_root) / "CURRENT_RUN.txt"
    if pointer.is_file():
        try:
            p = Path(pointer.read_text(encoding="utf-8").strip())
            if p.is_dir():
                return p
        except OSError:
            pass
    hist = list_iteration_runs(Path(runs_root), limit=1)
    if hist and hist[0].get("dir"):
        return Path(str(hist[0]["dir"]))
    return None


def _resolve_active_run() -> Path | None:
    """Streamlit wrapper: latest publish unless human pinned an Inspect selection."""
    return resolve_active_run_dir(
        runs_dir(),
        session_active=st.session_state.get("studio_active_run"),
        pinned=bool(st.session_state.get("studio_run_pinned")),
    )


def _clear_run_pin() -> None:
    st.session_state.pop("studio_run_pinned", None)
    st.session_state.pop("twin_iter_pick", None)


def _pin_active_run(path: Path | str) -> None:
    st.session_state["studio_active_run"] = str(path)
    st.session_state["studio_run_pinned"] = True


def _resolve_viz_run(preferred: Path | None = None) -> tuple[Path | None, str | None]:
    """Prefer a run that has eplusout.csv and/or model.idf for Twin panes."""
    candidates: list[Path] = []
    for p in (preferred, _resolve_active_run()):
        if p is not None and p.is_dir():
            candidates.append(p)
    for h in list_iteration_runs(runs_dir(), limit=20):
        if h.get("dir"):
            candidates.append(Path(str(h["dir"])))
    seen: set[str] = set()

    def _key(c: Path) -> str:
        try:
            return str(c.resolve())
        except OSError:
            return str(c)

    # Pass 1: has eplusout
    for c in candidates:
        key = _key(c)
        if key in seen:
            continue
        seen.add(key)
        if (c / "eplusout.csv").is_file() or find_eplusout_csv(c) is not None:
            note = None
            if preferred is not None and _key(c) != _key(preferred):
                note = (
                    f"Active run `{preferred.name}` has no eplusout.csv — "
                    f"showing panes from `{c.name}`."
                )
            return c, note
    # Pass 2: IDF-only (geometry without sim yet)
    seen.clear()
    for c in candidates:
        key = _key(c)
        if key in seen:
            continue
        seen.add(key)
        if find_run_idf(c) is not None:
            note = None
            if preferred is not None and _key(c) != _key(preferred):
                note = f"Showing IDF geometry from `{c.name}` (no eplusout yet)."
            return c, note
    fallback = preferred or _resolve_active_run() or newest_run_with_eplusout(runs_dir())
    return fallback, None


def _render_08_panes(run_dir: Path, *, n_floors: int | None = None) -> None:
    st.subheader("EnergyPlus visualizer (browser)")
    st.caption(
        "Live progress from DinD → `progress.json` / console. "
        "**Building massing** comes from the published IDF (`model.idf`) — unique per run, "
        "not a hard-coded prototype. Zone colors appear when `eplusout.csv` maps by zone name. "
        "Agents: publish IDF + CSV to `runs/<id>/`."
    )

    viz_dir, viz_note = _resolve_viz_run(run_dir)
    if viz_dir is None:
        st.warning("No published Twin runs yet (need `model.idf` and/or `eplusout.csv`).")
        return
    if viz_note:
        st.info(viz_note)
    run_dir = viz_dir

    live = False
    try:
        info0 = read_run_progress(run_dir)
        live = str(info0.get("status") or "").lower() in {"running", "starting"}
    except Exception:
        live = False

    def _draw() -> None:
        info = read_run_progress(run_dir)
        if info.get("replay"):
            st.info("Demo replay — fixture eplusout.csv (no live Docker EnergyPlus run).")

        left, right = st.columns([2, 3])
        with left:
            st.markdown("**Manage simulation**")
            st.progress(min(100, max(0, int(info.get("progress") or 0))) / 100.0)
            st.caption(f"status={info.get('status')} · run_id={info.get('run_id')}")
            log = info.get("log_tail") or "(no eplusout.err / console log yet)"
            st.text_area(
                "EnergyPlus output",
                value=log,
                height=220,
                key=f"twin_ep_log_{run_dir.name}",
            )
        with right:
            ts = load_sim_timeseries(run_dir)
            if ts is None:
                nested = find_eplusout_csv(run_dir)
                ts = load_sim_timeseries(nested.parent) if nested else None
            if ts is not None and not ts.outdoor.empty:
                st.plotly_chart(
                    outdoor_figure(ts.outdoor),
                    width="stretch",
                    key=f"twin_oa_{run_dir.name}",
                )
            else:
                st.caption(
                    f"No outdoor timeseries yet — publish `eplusout.csv` under `runs/{run_dir.name}/`."
                )

        # IDF-driven 3D massing (unique per building / run)
        idf_path = find_run_idf(run_dir)
        zone_temps = zone_mean_temps_by_name(ts) if ts is not None else {}
        if idf_path is not None:
            try:
                geom = parse_idf_geometry(idf_path)
                summary = geom.summary()
                st.markdown("**Building geometry (from published IDF)**")
                st.caption(
                    "Geometry from published IDF surfaces (not Map-traced CAD). "
                    "Units: EnergyPlus meters. "
                    f"Surfaces={summary.get('n_surfaces')} · zones={summary.get('n_zones')} · "
                    f"file=`{idf_path.name}`."
                )
                if geom.surfaces:
                    st.plotly_chart(
                        idf_massing_figure(
                            geom,
                            zone_temps=zone_temps or None,
                            title=f"IDF massing — {run_dir.name}",
                        ),
                        width="stretch",
                        key=f"twin_idf_3d_{run_dir.name}",
                    )
                    if zone_temps:
                        st.caption("Surfaces colored by zone mean air temp from eplusout.csv.")
                    else:
                        st.caption("Neutral massing — publish eplusout.csv to color by zone temp.")
                else:
                    st.warning(f"IDF `{idf_path.name}` has no BuildingSurface:Detailed objects.")
            except Exception as exc:
                st.error(f"IDF geometry parse failed: {exc}")
        else:
            st.warning(
                f"No `model.idf` under `runs/{run_dir.name}/` — publish the EnergyPlus IDF "
                "with the run to see this building's massing (unique per site)."
            )
            # Legacy fallback schematic — never claim it is site geometry
            if ts is not None:
                roles = zone_mean_by_role(ts)
                if roles:
                    st.caption(
                        "Fallback: classic 5Zone prototype schematic only — "
                        "not this building's IDF. Publish model.idf for real massing."
                    )
                    floors = int(n_floors or 1)
                    profile = _profile() or {}
                    if floors < 2:
                        floors = int(
                            profile.get("number_of_floors")
                            or profile.get("floors")
                            or st.session_state.get("twin_floors")
                            or 1
                        )
                    if floors >= 2:
                        st.plotly_chart(
                            multifloor_office_figure(roles, n_floors=floors),
                            width="stretch",
                            key=f"twin_multifloor_{run_dir.name}",
                        )
                        st.caption(MULTIFLOOR_HONESTY.replace("N-story", f"{floors}-story"))
                    else:
                        st.plotly_chart(
                            floor_plan_figure(roles),
                            width="stretch",
                            key=f"twin_floor_{run_dir.name}",
                        )

        if ts is not None:
            means = ts.zone_mean_temps()
            if not means.empty:
                st.dataframe(means, width="stretch", hide_index=True)

    if live:
        try:
            from datetime import timedelta

            @st.fragment(run_every=timedelta(seconds=2))
            def _live_draw() -> None:
                _draw()

            _live_draw()
        except Exception:
            _draw()
    else:
        _draw()


def render() -> None:
    st.header("Twin / calibrate — EnergyPlus vs bills")
    st.caption(
        "Resolve building inputs from the dump / campus data model (no city hardcodes). "
        "Dry-run or Docker EnergyPlus; AI agents outside Streamlit publish iterations to "
        "`runs/` so this browser page shows APIHelper-08 progress, OA, and floor-plan panes."
    )

    if st.button("Refresh agent runs", key="twin_refresh_runs"):
        _clear_run_pin()
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
        answers = st.session_state.get("studio_answers")
        from wattlab.studio.status import required_gaps_still_missing, soften_required_gaps

        soft = soften_required_gaps(gaps, answers if isinstance(answers, dict) else None)
        missing = required_gaps_still_missing(gaps, answers if isinstance(answers, dict) else None)
        answered_via = [
            g for g in soft
            if g.get("severity") == "required" and g.get("status") == "answered" and g.get("via")
        ]
        if missing:
            st.warning("Dump still missing: " + ", ".join(g["field"] for g in missing))
        elif answered_via:
            st.info(
                "Dump seed nulls covered by answers.json: "
                + ", ".join(g["field"] for g in answered_via)
            )

    profile = _profile()
    active_preview = _resolve_active_run()
    _render_eui_index(
        profile=profile,
        run_dir=active_preview,
        chart_key="twin_eui_index_active",
    )
    st.divider()

    if not profile:
        st.info(
            "Resolve a profile above (or have an AI agent write answers.json → wattlab twin). "
            "Agent prompt: vibe20_agent_spec/AGENT_TESTER_PROMPT.md"
        )
        # Still show any published 08 panes so agent work is visible before profile
        if active_preview is not None:
            _render_08_panes(active_preview)
        return

    with st.expander("Resolved profile", expanded=False):
        st.json(profile)

    try:
        from wattlab.energyplus.mcp import capability_status

        cap = capability_status(probe_docker=True)
        mode = cap.get("capability") or "?"
        if mode == "ready":
            st.success(
                f"EnergyPlus MCP: **{mode}** — DinD sims + dial-loads/mcp-exec inspect/modify OK."
            )
        else:
            st.warning(
                f"EnergyPlus MCP: **{mode}** — run `wattlab energyplus-ensure`. "
                f"{cap.get('note') or ''}"
            )
    except Exception as exc:
        st.caption(f"capability_status unavailable: {exc}")

    st.markdown("**Hard-size constrain (optional FM nameplate)**")
    st.caption(
        "Sparse ladder step 3: after autosize, freeze plant/fans toward FM tons/hp "
        "(conceptual). When target floor area ≫ prototype (~10k ft²), nameplate is "
        "scaled by 1/prototype_area_scale before factoring. Factors outside "
        "[0.25, 4.0] refuse freeze (NEEDS_INPUT — site geometry or Ideal Loads). "
        "Leave blank to keep autosize-only."
    )
    hs1, hs2 = st.columns(2)
    cooling_tons = hs1.number_input(
        "cooling_tons (nameplate)",
        min_value=0.0,
        value=0.0,
        step=10.0,
        key="twin_cooling_tons",
        help="e.g. 200 for 2×100 ton chillers — scaled down when site ≫ prototype",
    )
    fan_hp = hs2.number_input(
        "supply_fan_hp (nameplate)",
        min_value=0.0,
        value=0.0,
        step=5.0,
        key="twin_fan_hp",
        help="e.g. 75 hp — scaled with area when site ≫ prototype",
    )

    measure_set = st.session_state.get("studio_measure_set") or profile.get("measure_set") or "best"
    proxies = st.session_state.get("studio_proxies") or {}
    run_profile = dict(profile)
    run_profile["measure_set"] = measure_set
    if proxies:
        run_profile["proxy_savings"] = proxies
    hard_size: dict[str, float] = {}
    if cooling_tons and float(cooling_tons) > 0:
        hard_size["cooling_tons"] = float(cooling_tons)
    if fan_hp and float(fan_hp) > 0:
        hard_size["fan_hp"] = float(fan_hp)
    if hard_size:
        ep = dict(run_profile.get("energyplus") or {})
        ep["hard_size"] = hard_size
        run_profile["energyplus"] = ep
        run_profile["hard_size"] = hard_size

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
        from threading import Thread
        import time

        from wattlab.easy_button import run_easy_button
        from wattlab.energyplus.docker import write_progress

        if not img_ok:
            st.error(f"Cannot run: `{DOCKER_IMAGE}` missing. Use dry-run or demo replay.")
        else:
            # Claim run id early so 08 panes can poll progress while DinD runs.
            from datetime import datetime, timezone

            rid = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            dest = runs_dir() / rid
            dest.mkdir(parents=True, exist_ok=True)
            write_progress(dest, percent=0, status="running", note="Studio Twin DinD")
            st.session_state["studio_active_run"] = str(dest)
            box: dict[str, Any] = {"report": None, "exc": None}

            def _worker() -> None:
                try:
                    box["report"] = run_easy_button(
                        profile=run_profile,
                        measure_set=measure_set,
                        progress_dir=dest,
                    )
                except Exception as exc:  # noqa: BLE001
                    box["exc"] = exc

            thr = Thread(target=_worker, daemon=True)
            thr.start()
            status_box = st.empty()
            while thr.is_alive():
                info = read_run_progress(dest)
                with status_box.container():
                    st.progress(min(100, max(0, int(info.get("progress") or 0))) / 100.0)
                    st.caption(
                        f"Live DinD · status={info.get('status')} · "
                        f"{info.get('progress')}% · run_id={rid}"
                    )
                time.sleep(1.0)
            thr.join(timeout=5)
            if box["exc"] is not None:
                write_progress(dest, percent=0, status="failed", note=str(box["exc"]))
                st.error(f"EnergyPlus run failed: {box['exc']}")
            else:
                report = box["report"] or {}
                st.session_state["studio_report"] = report
                art = Path(
                    report.get("studio_run_dir")
                    or report.get("artifacts_dir")
                    or report.get("artifact_dir")
                    or ""
                )
                try:
                    if art.is_dir():
                        published = publish_run_for_studio(art, run_id=rid, report=report)
                        st.session_state["studio_active_run"] = str(published)
                        st.success(f"Run published for browser Twin panes → {published}")
                    else:
                        st.session_state["studio_active_run"] = str(dest)
                        st.success(f"Run finished → {dest}")
                except Exception as exc:
                    st.error(f"Publish failed: {exc}")
                st.rerun()

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
        sizing = report.get("sizing_scenario")
        if sizing == "hard_size_refused":
            refuse_note = None
            for p in report.get("patches") or []:
                if p.get("patch") == "hard_size" and p.get("needs_input"):
                    refuse_note = p.get("note")
                    break
                if p.get("hard_size_refused"):
                    refuse_note = p.get("refuse_reason")
                    break
            st.error(
                "Hard-size **refused** (NEEDS_INPUT): capacity factors outside "
                "[0.25, 4.0] after area scaling — kept autosize. "
                f"{refuse_note or 'Provide site geometry or Ideal Loads.'}"
            )
        elif sizing == "hard_size":
            st.info("Hard-size freeze applied (area-aware nameplate factors).")
        savings = report.get("savings_by_measure") or []
        if savings:
            st.dataframe(pd.json_normalize(savings), width="stretch", hide_index=True)
            peak_rows = [s for s in savings if s.get("peak_demand_kw") is not None]
            if peak_rows:
                st.caption(
                    "Peak demand (kW) shown alongside energy — from eplustbl Demand "
                    "tables or max hourly Electricity:Facility when present."
                )
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

    st.subheader("Modeled vs actual fuel")
    ub_path = st.session_state.get("studio_utility_bills_path")
    scorecard_path = st.text_input(
        "calibration_scorecard.json (optional)",
        key="twin_scorecard",
        placeholder=str(ARTIFACTS / "…/calibration_scorecard.json"),
    )
    bills_rows: list[dict[str, Any]] = []
    monthly_model: list[dict[str, Any]] = []
    scorecard: dict[str, Any] = {}

    def _load_scorecard(sc: dict[str, Any]) -> list[dict[str, Any]]:
        rows = list((sc.get("utility_bills") or {}).get("per_month") or [])
        for pm in rows:
            if pm.get("modeled_kwh") is None and pm.get("simulated_kwh") is not None:
                pm["modeled_kwh"] = pm["simulated_kwh"]
        return rows

    if scorecard_path.strip():
        sp = Path(scorecard_path.strip())
        if sp.is_file():
            try:
                scorecard = json.loads(sp.read_text(encoding="utf-8"))
                bills_rows = _load_scorecard(scorecard)
                monthly_model = list((scorecard.get("annual") or {}).get("monthly") or [])
                st.caption(
                    f"G14 status={scorecard.get('status')} · pass_fail="
                    f"{(scorecard.get('utility_bills') or {}).get('pass_fail')} · "
                    f"scale={scorecard.get('g14_scale') or scorecard.get('prototype_area_scale')}"
                )
            except Exception as exc:
                st.warning(f"scorecard read failed: {exc}")
    else:
        active_sc = _resolve_active_run()
        if active_sc is not None:
            for name in ("calibration_scorecard.json", "campaign_stamp.json"):
                sp = Path(active_sc) / name
                if not sp.is_file():
                    continue
                try:
                    sc = json.loads(sp.read_text(encoding="utf-8"))
                    if name == "campaign_stamp.json" and sc.get("scorecard_path"):
                        sp2 = Path(sc["scorecard_path"])
                        if sp2.is_file():
                            sc = json.loads(sp2.read_text(encoding="utf-8"))
                    scorecard = sc
                    bills_rows = _load_scorecard(sc)
                    monthly_model = list((sc.get("annual") or {}).get("monthly") or [])
                    if bills_rows or sc.get("status"):
                        st.caption(
                            f"Autoloaded scorecard · status={sc.get('status')} · "
                            f"pass_fail={(sc.get('utility_bills') or {}).get('pass_fail')}"
                        )
                    break
                except Exception:
                    continue

    if bundle is not None and not getattr(bundle, "utility_bills", pd.DataFrame()).empty:
        ub = bundle.utility_bills
        st.caption("utility_bills from dump / energy bridge")
        st.dataframe(ub.head(24), width="stretch", hide_index=True)
    elif ub_path and Path(ub_path).is_file():
        ub = pd.read_csv(ub_path)
        st.caption(f"utility_bills bridge → {ub_path}")
        st.dataframe(ub.head(24), width="stretch", hide_index=True)

    if bills_rows:
        import plotly.graph_objects as go

        bdf = pd.DataFrame(bills_rows)
        st.dataframe(bdf, width="stretch", hide_index=True)
        if "observed_kwh" in bdf.columns and "modeled_kwh" in bdf.columns:
            plot_df = bdf.copy()
            if "month" in plot_df.columns:
                # Prefer Jan…Dec labels when values look like month numbers / MM
                mo = plot_df["month"].astype(str)
                if mo.str.fullmatch(r"\d{1,2}").all() or mo.str.fullmatch(r"\d{4}-\d{2}").all():
                    if mo.str.fullmatch(r"\d{1,2}").all():
                        x_labels = [month_abbrev(m) for m in mo]
                    else:
                        x_labels = [
                            f"{m[:4]}-{month_abbrev(m[5:7])}" if len(m) >= 7 else m for m in mo
                        ]
                else:
                    x_labels = mo.tolist()
            else:
                x_labels = list(range(len(plot_df)))
            fig_cal = go.Figure()
            fig_cal.add_scatter(
                x=x_labels,
                y=plot_df["observed_kwh"],
                mode="lines+markers",
                name="Bills (observed)",
                line=dict(color="#1f77b4"),
            )
            fig_cal.add_scatter(
                x=x_labels,
                y=plot_df["modeled_kwh"],
                mode="lines+markers",
                name="Model (calibrated)",
                line=dict(color="#d62728"),
            )
            fig_cal.update_layout(
                title="Monthly electricity — bills vs model",
                height=360,
                margin=dict(l=10, r=10, t=40, b=10),
                yaxis_title="kWh",
                legend=dict(orientation="h", y=1.12),
            )
            st.plotly_chart(fig_cal, width="stretch", key="twin_cal_overlay")
        ubills = scorecard.get("utility_bills") or {}
        stats = ubills.get("stats_electricity") or ubills.get("stats") or {}
        if stats:
            g1, g2, g3 = st.columns(3)
            g1.metric("G14 NMBE %", f"{stats.get('nmbe_pct', '—')}")
            g2.metric("G14 CV(RMSE) %", f"{stats.get('cvrmse_pct', '—')}")
            g3.metric("Pass/fail", str(ubills.get("pass_fail") or "—"))
        from wattlab.studio.monthly_pct_off import (
            build_monthly_pct_off,
            render_monthly_pct_off_panel,
        )

        render_monthly_pct_off_panel(build_monthly_pct_off(bills_rows))
    elif monthly_model:
        st.dataframe(pd.DataFrame(monthly_model).head(24), width="stretch", hide_index=True)

    st.subheader("Client deliverables")
    st.caption(
        "Professional handoff: executive report, results workbook, and model package "
        "(IDF / EPW / selected EnergyPlus outputs). Screening or calibrated — stamped honestly."
    )
    studio_report = st.session_state.get("studio_report") or {}
    profile = _profile() or {}
    build_col, hint_col = st.columns([1, 2])
    with build_col:
        build_clicked = st.button(
            "Build client package",
            key="twin_build_deliverable",
            type="primary",
            help="Creates report.md + results.xlsx + zip under reports/",
        )
    with hint_col:
        st.caption(
            "Uses the active Twin run + calibration scorecard when present. "
            "Agents can also run `wattlab calibrate-campaign` then refresh."
        )
    if build_clicked:
        from wattlab.deliverables import package_deliverables

        run_src = _resolve_active_run()
        sc = scorecard
        if not sc and run_src and (Path(run_src) / "calibration_scorecard.json").is_file():
            sc = json.loads(
                (Path(run_src) / "calibration_scorecard.json").read_text(encoding="utf-8")
            )
        if not sc and studio_report:
            sc = {
                "run_id": studio_report.get("run_id"),
                "status": "screening",
                "annual": ((studio_report.get("result_records") or [{}])[0] or {}).get("annual"),
                "weather_suitability": studio_report.get("weather_suitability"),
                "prototype_area_scale": studio_report.get("prototype_area_scale"),
                "sizing_scenario": studio_report.get("sizing_scenario"),
                "utility_bills": {},
            }
        if not sc and not studio_report and run_src is None:
            st.warning("No scorecard or published run yet — run Twin / calibrate-campaign first.")
        else:
            rid = (sc or {}).get("run_id") or (Path(run_src).name if run_src else "latest")
            dest = reports_dir() / f"deliverable_{rid}"
            try:
                meta = package_deliverables(
                    out_dir=dest,
                    run_dir=Path(run_src) if run_src else None,
                    scorecard=sc or {},
                    report=studio_report or None,
                    profile=profile,
                )
                st.session_state["studio_deliverable"] = meta
                st.success(f"Package ready → `{meta.get('out_dir')}`")
            except Exception as exc:
                st.error(f"Deliverable build failed: {exc}")

    deliv = st.session_state.get("studio_deliverable") or {}
    if deliv.get("report_md") and Path(str(deliv["report_md"])).is_file():
        tab_report, tab_files = st.tabs(["Report preview", "Downloads"])
        md_text = Path(str(deliv["report_md"])).read_text(encoding="utf-8")
        with tab_report:
            st.markdown(md_text)
        with tab_files:
            stamp = (deliv.get("stamp") or {})
            if stamp:
                st.json(stamp, expanded=False)
            d1, d2, d3 = st.columns(3)
            d1.download_button(
                "Report (.md)",
                data=md_text.encode("utf-8"),
                file_name="Energy_Modeling_Report.md",
                mime="text/markdown",
                key="dl_report_md",
            )
            xlsx_p = deliv.get("workbook_xlsx")
            if xlsx_p and Path(str(xlsx_p)).is_file():
                d2.download_button(
                    "Results workbook (.xlsx)",
                    data=Path(str(xlsx_p)).read_bytes(),
                    file_name="Energy_Model_Results.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_workbook_xlsx",
                )
            zip_p = deliv.get("zip_path")
            if zip_p and Path(str(zip_p)).is_file():
                d3.download_button(
                    "Full package (.zip)",
                    data=Path(str(zip_p)).read_bytes(),
                    file_name=Path(str(zip_p)).name,
                    mime="application/zip",
                    key="dl_deliverable_zip",
                )
            st.caption(
                "Zip: `01_Report` · `02_Results` · `03_Models` · `04_Outputs` · "
                "`05_Source_Data` · `06_Documentation` — or download report/workbook alone."
            )

    st.divider()
    with st.container(border=True):
        st.subheader("Iteration history (agent + Studio)")
        st.caption(
            "Each published `runs/<id>/` after agent/CLI EnergyPlus. "
            "Timestamps from `run_manifest.json`. G14 columns need `calibration_scorecard.json` per run."
        )
        from wattlab.studio.g14_history import g14_epoch_figure, iter_g14_history
        from wattlab.studio.model_summary import (
            build_assumption_rows,
            build_model_summary,
            render_model_summary_panel,
        )

        hist = list_iteration_runs(runs_dir(), limit=30)
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
                            "started_at": m.get("started_at"),
                            "finished_at": m.get("finished_at"),
                            "elapsed_s": None,
                            "hypothesis": m.get("hypothesis") or m.get("notes"),
                        }
                    )
                except Exception:
                    continue
        if not hist:
            st.caption("No prior runs in workspace runs/.")
        else:
            st.metric("Published iterations shown", len(hist))
            g14_rows = iter_g14_history(runs_dir(), limit=30)
            g14_by_dir = {str(r.get("dir")): r for r in g14_rows if r.get("dir")}
            enriched = []
            for h in hist:
                dkey = str(h.get("dir") or "")
                g = g14_by_dir.get(dkey) or {}
                row = {
                    "started_at": h.get("started_at") or g.get("started_at"),
                    "run_id": h.get("run_id"),
                    "hypothesis": h.get("hypothesis"),
                    "weather": h.get("weather_mode"),
                    "status": h.get("status"),
                    "eplusout": "yes" if h.get("has_eplusout") else "no",
                    "elapsed_s": h.get("elapsed_s"),
                    "nmbe_elec_pct": g.get("nmbe_elec_pct"),
                    "cvrmse_elec_pct": g.get("cvrmse_elec_pct"),
                    "nmbe_gas_pct": g.get("nmbe_gas_pct"),
                    "cvrmse_gas_pct": g.get("cvrmse_gas_pct"),
                    "g14": g.get("pass_fail"),
                    "dir": h.get("dir"),
                }
                model = load_model_eui_from_run(Path(str(h["dir"])) if h.get("dir") else None)
                if model.get("model_eui_kbtu_ft2") is not None:
                    row["model_eui_kbtu_ft2"] = model["model_eui_kbtu_ft2"]
                if model.get("prototype_area_scale") is not None:
                    row["prototype_area_scale"] = model["prototype_area_scale"]
                if model.get("weather_mode") and not row.get("weather"):
                    row["weather"] = model["weather_mode"]
                if model.get("peak_demand_kw") is not None:
                    row["peak_demand_kw"] = model["peak_demand_kw"]
                if row.get("elapsed_s") is not None:
                    try:
                        row["elapsed_min"] = round(float(row["elapsed_s"]) / 60.0, 2)
                    except (TypeError, ValueError):
                        pass
                enriched.append(row)
            show_cols = [
                c
                for c in (
                    "started_at",
                    "run_id",
                    "hypothesis",
                    "status",
                    "eplusout",
                    "nmbe_elec_pct",
                    "cvrmse_elec_pct",
                    "nmbe_gas_pct",
                    "cvrmse_gas_pct",
                    "g14",
                    "model_eui_kbtu_ft2",
                    "elapsed_min",
                    "peak_demand_kw",
                    "prototype_area_scale",
                    "weather",
                )
                if any(c in r and r.get(c) is not None for r in enriched)
            ]
            st.dataframe(
                pd.DataFrame(enriched)[show_cols] if show_cols else pd.DataFrame(enriched),
                width="stretch",
                hide_index=True,
            )

            st.markdown("**Calibration iterations (G14)**")
            st.caption(
                "Like a training-loss curve: each published Twin run is an epoch. "
                "Lower |NMBE| / CV(RMSE) is better. "
                "**Dashed legend entries** are ASHRAE G14 monthly gates "
                "(±5% |NMBE|, ≤15% CVRMSE) — not extra model series. "
                "Missing scorecards skip that point."
            )
            st.plotly_chart(
                g14_epoch_figure(g14_rows, height=440),
                width="stretch",
                key="twin_g14_epoch",
            )

            pick_opts = [h.get("dir") for h in hist if h.get("dir")]
            active_now = _resolve_active_run()
            default_ix = 0
            if active_now is not None:
                active_s = str(active_now.resolve()) if active_now.exists() else str(active_now)
                for i, d in enumerate(pick_opts):
                    try:
                        if d and str(Path(str(d)).resolve()) == active_s:
                            default_ix = i
                            break
                    except OSError:
                        if str(d) == str(active_now):
                            default_ix = i
                            break
            # Avoid Streamlit "value not in options" when runs/ was pruned
            cur_pick = st.session_state.get("twin_iter_pick")
            if cur_pick is not None and cur_pick not in pick_opts:
                st.session_state.pop("twin_iter_pick", None)
            if "twin_iter_pick" not in st.session_state and pick_opts:
                st.session_state["twin_iter_pick"] = pick_opts[default_ix]

            pick = st.selectbox(
                "Inspect iteration",
                options=pick_opts,
                format_func=lambda d: Path(str(d)).name if d else "",
                key="twin_iter_pick",
            )
            if pick:
                answers = st.session_state.get("studio_answers")
                if not isinstance(answers, dict):
                    answers = {}
                profile = _profile()
                summary = build_model_summary(answers, Path(str(pick)), profile=profile)
                rows = build_assumption_rows(
                    answers, Path(str(pick)), profile=profile, summary=summary
                )
                pin_note = (
                    "Pinned to this Inspect selection."
                    if st.session_state.get("studio_run_pinned")
                    else "Twin panes follow latest CURRENT_RUN unless you pin below."
                )
                with st.expander("Model assumptions (selected iteration)", expanded=True):
                    st.caption(pin_note)
                    render_model_summary_panel(summary, rows)
                    from wattlab.studio.monthly_pct_off import (
                        build_monthly_pct_off,
                        load_per_month_from_run,
                        render_monthly_pct_off_panel,
                    )

                    pct_analysis = build_monthly_pct_off(load_per_month_from_run(pick))
                    render_monthly_pct_off_panel(pct_analysis)
                if st.button("Show 08 panes for selection", key="twin_show_iter"):
                    _pin_active_run(pick)
                    st.rerun()

    st.divider()
    # EnergyPlus visualizer last — IDF massing / OA / progress
    viz_run = _resolve_active_run()
    if viz_run is not None:
        with st.container(border=True):
            _render_08_panes(viz_run)
    else:
        st.info(
            "No published Twin runs yet. An AI agent should write `runs/<id>/eplusout.csv` "
            "(or click demo replay / Docker run). See AGENT_TESTER_PROMPT.md."
        )
