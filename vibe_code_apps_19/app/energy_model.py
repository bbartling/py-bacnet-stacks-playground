"""OpenFDD WattLab Energy Model section for vibe19 Streamlit.

Responsive-defaults minimal form → WattLab defaults engine (vibe20) → EnergyPlus Docker runs.
Apps stay decoupled: file reads + subprocess only (no cross-imports).
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# WattLab directory resolution
# ---------------------------------------------------------------------------


def resolve_wattlab_dir() -> Path | None:
    env = (os.environ.get("VIBE19_WATTLAB_DIR") or "").strip()
    if env:
        p = Path(env)
        if (p / "easy_button.py").is_file():
            return p.resolve()
    # Sibling default: .../vibe_code_apps_19 → .../vibe_code_apps_20
    here = Path(__file__).resolve().parents[1]  # vibe_code_apps_19
    sibling = here.parent / "vibe_code_apps_20"
    if (sibling / "easy_button.py").is_file():
        return sibling.resolve()
    return None


def wattlab_status(wattlab: Path | None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "wattlab_dir": str(wattlab) if wattlab else None,
        "easy_button": False,
        "docker_hint": "Set VIBE19_WATTLAB_DIR and ensure Docker image energyplus-mcp-dev is present.",
    }
    if not wattlab:
        return out
    out["easy_button"] = (wattlab / "easy_button.py").is_file()
    return out


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_form_options(wattlab: Path) -> dict[str, Any]:
    arch = _load_json(wattlab / "defaults" / "archetypes.json")
    clim = _load_json(wattlab / "defaults" / "climate.json")
    codes = _load_json(wattlab / "defaults" / "codes.json")
    sets_path = wattlab / "ecm_library" / "measure_sets.json"
    sets = _load_json(sets_path) if sets_path.is_file() else {}
    return {
        "building_types": [
            {"id": k, "label": v.get("label") or k, **{kk: vv for kk, vv in v.items() if kk != "label"}}
            for k, v in arch.items()
            if isinstance(v, dict) and "label" in v
        ],
        "cities": [
            {"id": k, "label": v.get("label") or k, "climate_zone": v.get("climate_zone") or ""}
            for k, v in (clim.get("cities") or {}).items()
        ],
        "codes": [
            {"id": k, "label": v.get("label") or k}
            for k, v in (codes.get("codes") or {}).items()
        ],
        "measure_sets": [
            {
                "id": k,
                "label": (sets.get(k) or {}).get("label") or k,
                "description": (sets.get(k) or {}).get("description") or "",
            }
            for k in ("good", "better", "best")
            if k in sets
        ],
        "default_city": clim.get("default_city") or "madison",
        "default_code": codes.get("default_code") or "ashrae_90.1_2013",
    }


def _run_python(wattlab: Path, args: list[str], *, timeout: int = 600) -> dict[str, Any]:
    cmd = [os.environ.get("VIBE19_WATTLAB_PYTHON") or "python", *args]
    proc = subprocess.run(
        cmd,
        cwd=str(wattlab),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    stdout = proc.stdout or ""
    # Prefer last JSON object in stdout
    report = None
    try:
        report = json.loads(stdout)
    except json.JSONDecodeError:
        # find last {...}
        start = stdout.rfind("{")
        if start >= 0:
            try:
                report = json.loads(stdout[start:])
            except json.JSONDecodeError:
                report = None
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": stdout[-8000:],
        "stderr": (proc.stderr or "")[-4000:],
        "report": report,
    }


def resolve_via_cli(wattlab: Path, minimal: dict[str, Any]) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(minimal, f)
        tmp = Path(f.name)
    try:
        # Use wattlab_defaults as module script
        code = (
            "import json,sys; from wattlab_defaults import resolve_profile; "
            f"print(json.dumps(resolve_profile(json.load(open(r'{tmp}', encoding='utf-8')))))"
        )
        return _run_python(wattlab, ["-c", code], timeout=60)
    finally:
        tmp.unlink(missing_ok=True)


def run_easy_button(
    wattlab: Path,
    *,
    profile: dict[str, Any],
    measure_set: str | None,
    dry_run: bool = False,
    timeout: int = 1800,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as td:
        profile_path = Path(td) / "building_profile.json"
        profile_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
        args = ["easy_button.py", "--building", str(profile_path)]
        if measure_set:
            args.extend(["--measure-set", measure_set])
        if dry_run:
            args.append("--dry-run")
        return _run_python(wattlab, args, timeout=timeout)


def write_fdd_bundle_from_session(
    out_dir: Path,
    *,
    batch_results: list | None,
    results_summary_fn,
) -> Path:
    """Write a minimal vibe19-style bundle for vibe19_bridge."""
    out_dir.mkdir(parents=True, exist_ok=True)
    if batch_results:
        summary = results_summary_fn(batch_results)
        if isinstance(summary, pd.DataFrame):
            summary.to_csv(out_dir / "fdd_summary.csv", index=False)
    else:
        (out_dir / "fdd_summary.csv").write_text(
            "rule_id,equipment_id,equipment_type,status,applicable,fault_hours,fault_pct,notes\n",
            encoding="utf-8",
        )
    return out_dir


def bridge_suggest(wattlab: Path, bundle_dir: Path) -> dict[str, Any]:
    return _run_python(
        wattlab,
        ["vibe19_bridge.py", str(bundle_dir)],
        timeout=60,
    )


# ---------------------------------------------------------------------------
# Geometry / charts
# ---------------------------------------------------------------------------


def rectangular_massing(
    area_ft2: float,
    floors: int,
    floor_to_floor_ft: float,
    wwr: float,
    aspect_ratio: float = 1.5,
) -> dict[str, Any]:
    """Simple rectangular shell dimensions for Plotly 3D massing."""
    floors = max(1, int(floors))
    floor_area = float(area_ft2) / floors
    # L * W = floor_area, L/W = aspect
    width = math.sqrt(floor_area / aspect_ratio)
    length = floor_area / width
    height = floors * float(floor_to_floor_ft)
    return {
        "length_ft": round(length, 1),
        "width_ft": round(width, 1),
        "height_ft": round(height, 1),
        "floors": floors,
        "wwr": float(wwr),
        "floor_area_ft2": round(floor_area, 0),
        "gross_area_ft2": float(area_ft2),
    }


def massing_figure(dims: dict[str, Any]):
    """Plotly Mesh3d rectangular building massing."""
    import plotly.graph_objects as go

    L = dims["length_ft"]
    W = dims["width_ft"]
    H = dims["height_ft"]
    # box corners
    x = [0, L, L, 0, 0, L, L, 0]
    y = [0, 0, W, W, 0, 0, W, W]
    z = [0, 0, 0, 0, H, H, H, H]
    i = [0, 0, 4, 4, 0, 0, 1, 1, 2, 2, 3, 3]
    j = [1, 2, 5, 6, 1, 5, 2, 6, 3, 7, 0, 4]
    k = [2, 3, 6, 7, 5, 4, 6, 5, 7, 6, 4, 7]
    fig = go.Figure(
        data=[
            go.Mesh3d(
                x=x,
                y=y,
                z=z,
                i=i,
                j=j,
                k=k,
                opacity=0.55,
                color="#4C78A8",
                name="shell",
            )
        ]
    )
    # floor plates
    for f in range(1, int(dims["floors"])):
        zf = f * (H / dims["floors"])
        fig.add_trace(
            go.Scatter3d(
                x=[0, L, L, 0, 0],
                y=[0, 0, W, W, 0],
                z=[zf] * 5,
                mode="lines",
                line=dict(color="#888", width=2),
                showlegend=False,
            )
        )
    fig.update_layout(
        title=f"Conceptual massing · WWR {dims['wwr']:.0%} · {dims['gross_area_ft2']:,.0f} ft²",
        scene=dict(
            xaxis_title="Length (ft)",
            yaxis_title="Width (ft)",
            zaxis_title="Height (ft)",
            aspectmode="data",
        ),
        margin=dict(l=0, r=0, t=40, b=0),
        height=420,
    )
    return fig


def savings_waterfall_figure(savings: list[dict[str, Any]]):
    import plotly.graph_objects as go

    if not savings:
        return None
    labels = [r.get("measure_id") or f"step{i}" for i, r in enumerate(savings)]
    # Cumulative kWh saved vs baseline
    y = []
    for r in savings:
        vb = (r.get("vs_baseline") or {}).get("kwh_saved")
        y.append(vb if vb is not None else 0)
    fig = go.Figure(
        go.Waterfall(
            x=labels,
            y=y,
            measure=["absolute"] + ["relative"] * (len(labels) - 1) if len(labels) > 1 else ["absolute"],
            text=[f"{v:,.0f}" if v else "0" for v in y],
            connector={"line": {"color": "#888"}},
        )
    )
    # Absolute cumulative is clearer — recompute as absolute values
    fig = go.Figure(
        data=[
            go.Bar(
                x=labels,
                y=y,
                marker_color=["#999" if i == 0 else "#59A14F" for i in range(len(labels))],
                text=[f"{v:,.0f} kWh" for v in y],
                textposition="outside",
            )
        ]
    )
    fig.update_layout(
        title="Cumulative kWh savings vs baseline (progressive measures)",
        yaxis_title="kWh saved",
        height=360,
        margin=dict(t=50, b=40),
    )
    return fig


def monthly_bar_figure(result_records: list[dict[str, Any]]):
    import plotly.graph_objects as go

    # Use final case monthly if present, else baseline
    rec = result_records[-1] if result_records else None
    if not rec:
        return None
    monthly = rec.get("monthly") or []
    if not monthly:
        return None
    months = [m.get("month_name") or m.get("month") for m in monthly]
    kwh = [m.get("electricity_kwh") or 0 for m in monthly]
    fig = go.Figure(data=[go.Bar(x=months, y=kwh, name="Electricity kWh")])
    fig.update_layout(
        title=f"Monthly electricity — {rec.get('measure_id') or 'baseline'}",
        yaxis_title="kWh",
        height=340,
        margin=dict(t=50, b=40),
    )
    return fig


# ---------------------------------------------------------------------------
# Streamlit render
# ---------------------------------------------------------------------------


def render_energy_model_tab(
    *,
    batch_results: list | None = None,
    results_summary_fn=None,
) -> None:
    st.subheader("Energy Model · OpenFDD WattLab")
    st.caption(
        "Easy-button energy screen: enter what you know (type, area, city, HVAC family). "
        "Everything else uses responsive defaults. EnergyPlus **autosizes** capacities — "
        "you do not need fan sizes or plant tons. Runs via vibe20 Docker (EnergyPlus-MCP)."
    )

    wattlab = resolve_wattlab_dir()
    status = wattlab_status(wattlab)
    if not wattlab or not status["easy_button"]:
        st.warning(
            "WattLab (vibe_code_apps_20) not found. Set env **VIBE19_WATTLAB_DIR** to the "
            "vibe_code_apps_20 path (must contain `easy_button.py`), and build the "
            "`energyplus-mcp-dev` Docker image."
        )
        st.code(
            "set VIBE19_WATTLAB_DIR=C:\\path\\to\\vibe_code_apps_20\n"
            "cd %VIBE19_WATTLAB_DIR%\\third_party\\EnergyPlus-MCP\n"
            "# follow README to build energyplus-mcp-dev",
            language="bash",
        )
        return

    st.success(f"WattLab ready · `{wattlab}`")
    options = load_form_options(wattlab)

    # --- Form (Project + Design minimal) ---
    with st.expander("Building inputs (easy button)", expanded=True):
        c1, c2, c3 = st.columns(3)
        type_ids = [t["id"] for t in options["building_types"]]
        type_labels = {t["id"]: t["label"] for t in options["building_types"]}
        btype = c1.selectbox(
            "Building type",
            type_ids,
            format_func=lambda i: type_labels.get(i, i),
            index=type_ids.index("office") if "office" in type_ids else 0,
        )
        city_ids = [c["id"] for c in options["cities"]]
        city_labels = {
            c["id"]: f"{c['label']} ({c.get('climate_zone') or '?'})"
            for c in options["cities"]
        }
        default_city = options.get("default_city") or city_ids[0]
        city = c2.selectbox(
            "City",
            city_ids,
            format_func=lambda i: city_labels.get(i, i),
            index=city_ids.index(default_city) if default_city in city_ids else 0,
        )
        code_ids = [c["id"] for c in options["codes"]]
        code_labels = {c["id"]: c["label"] for c in options["codes"]}
        default_code = options.get("default_code") or code_ids[0]
        code = c3.selectbox(
            "Energy code vintage",
            code_ids,
            format_func=lambda i: code_labels.get(i, i),
            index=code_ids.index(default_code) if default_code in code_ids else 0,
        )

        arch = next((t for t in options["building_types"] if t["id"] == btype), {})
        d1, d2, d3, d4 = st.columns(4)
        area = d1.number_input(
            "Gross floor area (ft²)",
            min_value=1000.0,
            value=float(arch.get("default_area_ft2") or 50000),
            step=1000.0,
        )
        floors = d2.number_input(
            "Floors",
            min_value=1,
            value=int(arch.get("default_floors") or 3),
            step=1,
        )
        ftf = d3.number_input(
            "Floor-to-floor (ft)",
            min_value=8.0,
            value=float(arch.get("default_floor_to_floor_ft") or 13.0),
            step=0.5,
        )
        wwr = d4.number_input(
            "Window-wall ratio",
            min_value=0.0,
            max_value=0.95,
            value=float(arch.get("default_wwr") or 0.33),
            step=0.05,
        )
        st.caption("Blue-style defaults: change type/city/code above to refresh archetype values.")

        hvac_def = arch.get("hvac_defaults") or {}
        hopts = arch.get("hvac_options") or {}
        fuel_opts = list(hopts.get("fuel") or ["gas", "electric"])
        air_opts = list(hopts.get("airside") or ["vav_reheat", "psz_ac", "cAV"])
        plant_opts = list(hopts.get("plant") or ["air_cooled_chiller", "dx", "none"])
        h1, h2, h3 = st.columns(3)
        fuel = h1.selectbox(
            "HVAC fuel",
            fuel_opts,
            index=fuel_opts.index(hvac_def["fuel"])
            if hvac_def.get("fuel") in fuel_opts
            else 0,
        )
        airside = h2.selectbox(
            "Air-side system",
            air_opts,
            index=air_opts.index(hvac_def["airside"])
            if hvac_def.get("airside") in air_opts
            else 0,
        )
        plant = h3.selectbox(
            "Cooling plant",
            plant_opts,
            index=plant_opts.index(hvac_def["plant"])
            if hvac_def.get("plant") in plant_opts
            else 0,
        )

        u1, u2 = st.columns(2)
        elec = u1.number_input("Electricity $/kWh", min_value=0.01, value=0.12, step=0.01)
        gas = u2.number_input("Gas $/therm", min_value=0.01, value=0.80, step=0.05)

        set_ids = [s["id"] for s in options["measure_sets"]] or ["good", "better", "best"]
        set_labels = {s["id"]: f"{s['label']} — {s.get('description') or ''}" for s in options["measure_sets"]}
        measure_set = st.selectbox(
            "Measure set (Good / Better / Best)",
            set_ids,
            format_func=lambda i: set_labels.get(i, i),
            index=set_ids.index("best") if "best" in set_ids else 0,
        )

    minimal = {
        "building_type": btype,
        "city": city,
        "code_year": code,
        "floor_area_ft2": float(area),
        "floors": int(floors),
        "floor_to_floor_ft": float(ftf),
        "wwr": float(wwr),
        "hvac": {"fuel": fuel, "airside": airside, "plant": plant},
        "utility": {"elec_usd_per_kwh": float(elec), "gas_usd_per_therm": float(gas)},
        "measure_set": measure_set,
        "anonymized": True,
    }

    # Massing preview
    dims = rectangular_massing(float(area), int(floors), float(ftf), float(wwr))
    m1, m2 = st.columns([1.2, 1])
    with m1:
        st.plotly_chart(massing_figure(dims), use_container_width=True)
    with m2:
        st.markdown("##### Shell summary")
        st.write(
            f"- **{dims['length_ft']} × {dims['width_ft']} ft** floorplate  \n"
            f"- **{dims['floors']} floors** · **{dims['height_ft']} ft** tall  \n"
            f"- WWR **{dims['wwr']:.0%}** · **{dims['gross_area_ft2']:,.0f} ft²** gross  \n"
            f"- HVAC **{fuel} / {airside} / {plant}** (autosized — no capacity inputs)"
        )
        if st.button("Preview resolved defaults", key="wattlab_preview_defaults"):
            with st.spinner("Resolving WattLab defaults…"):
                res = resolve_via_cli(wattlab, minimal)
            if res.get("report"):
                profile = res["report"]
                st.session_state["wattlab_resolved_profile"] = profile
                fs = profile.get("field_sources") or {}
                rows = [
                    {
                        "field": k,
                        "value": (v or {}).get("value"),
                        "source": (v or {}).get("source"),
                        "note": (v or {}).get("note") or "",
                    }
                    for k, v in fs.items()
                ]
                st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
                st.caption(profile.get("energyplus", {}).get("epw_note") or "")
            else:
                st.error("Defaults resolve failed")
                st.code(res.get("stderr") or res.get("stdout") or "")

    # FDD → measures
    st.markdown("##### Suggest measures from OpenFDD results")
    sug_col1, sug_col2 = st.columns([1, 2])
    with sug_col1:
        if st.button(
            "Suggest from current FDD results",
            key="wattlab_suggest_fdd",
            disabled=not batch_results,
        ):
            if not results_summary_fn:
                st.error("results_summary_fn missing")
            else:
                with tempfile.TemporaryDirectory() as td:
                    bundle = write_fdd_bundle_from_session(
                        Path(td),
                        batch_results=batch_results,
                        results_summary_fn=results_summary_fn,
                    )
                    with st.spinner("Bridging vibe19 → WattLab measures…"):
                        br = bridge_suggest(wattlab, bundle)
                if br.get("report"):
                    bridge = br["report"].get("bridge") or br["report"]
                    st.session_state["wattlab_bridge"] = bridge
                    st.success(
                        f"Suggested {len(bridge.get('measure_ids') or [])} measures: "
                        f"{', '.join(bridge.get('measure_ids') or [])}"
                    )
                else:
                    st.error("Bridge failed")
                    st.code(br.get("stderr") or br.get("stdout") or "")
        if not batch_results:
            st.caption("Run rules first (Run Rules section) to enable FDD-based suggestions.")
    with sug_col2:
        bridge = st.session_state.get("wattlab_bridge")
        if bridge:
            st.json(
                {
                    "measure_ids": bridge.get("measure_ids"),
                    "stats": bridge.get("stats"),
                    "evidence_count": len(bridge.get("evidence") or []),
                }
            )

    # Run
    st.markdown("##### Run EnergyPlus screening")
    r1, r2, r3 = st.columns(3)
    run_baseline = r1.button("Run baseline only", key="wattlab_run_base")
    run_set = r2.button(
        f"Run baseline + {measure_set} set",
        key="wattlab_run_set",
        type="primary",
    )
    run_dry = r3.button("Dry-run plan", key="wattlab_dry")

    def _prepare_profile() -> tuple[dict[str, Any], str | None]:
        res = resolve_via_cli(wattlab, minimal)
        if not res.get("report"):
            raise RuntimeError(res.get("stderr") or res.get("stdout") or "resolve failed")
        profile = res["report"]
        use_set: str | None = measure_set
        bridge = st.session_state.get("wattlab_bridge")
        if bridge and bridge.get("measures"):
            # Prefer FDD-suggested measures over measure_set if user ran suggest
            profile["measures"] = bridge["measures"]
            # Clear measure_set so easy_button uses explicit measures
            profile.pop("measure_set", None)
            use_set = None
        st.session_state["wattlab_resolved_profile"] = profile
        return profile, use_set

    if run_dry or run_baseline or run_set:
        try:
            profile, use_set = _prepare_profile()
            if run_dry:
                with st.spinner("Dry-run…"):
                    out = run_easy_button(
                        wattlab, profile=profile, measure_set=use_set, dry_run=True
                    )
                st.session_state["wattlab_last_report"] = out.get("report")
            elif run_baseline:
                # baseline only: empty measures
                profile = dict(profile)
                profile["measures"] = []
                profile.pop("measure_set", None)
                with st.spinner(
                    "Running EnergyPlus baseline (Docker) — this may take a few minutes…"
                ):
                    out = run_easy_button(
                        wattlab, profile=profile, measure_set=None, dry_run=False
                    )
                st.session_state["wattlab_last_report"] = out.get("report")
                st.session_state["wattlab_last_run_meta"] = {
                    k: out.get(k) for k in ("ok", "returncode", "stderr")
                }
            else:
                with st.spinner(
                    f"Running EnergyPlus baseline + {use_set or 'measures'} "
                    "(Docker) — several sequential sims…"
                ):
                    out = run_easy_button(
                        wattlab,
                        profile=profile,
                        measure_set=use_set,
                        dry_run=False,
                    )
                st.session_state["wattlab_last_report"] = out.get("report")
                st.session_state["wattlab_last_run_meta"] = {
                    k: out.get(k) for k in ("ok", "returncode", "stderr")
                }
            if not out.get("ok") and not run_dry:
                st.warning("EnergyPlus run reported a non-zero exit — check logs below.")
                st.code(out.get("stderr") or "")
        except Exception as exc:
            st.exception(exc)

    report = st.session_state.get("wattlab_last_report")
    if report:
        st.markdown("##### Results")
        if report.get("dry_run"):
            st.json(report)
            return
        st.info(report.get("disclaimer") or "")
        records = report.get("result_records") or []
        if records:
            base = (records[0].get("annual") or {})
            final = (records[-1].get("annual") or {})
            c1, c2, c3, c4 = st.columns(4)
            c1.metric(
                "Site EUI",
                f"{final.get('site_eui_kbtu_ft2_year') or '—'} kBtu/ft²",
                delta=(
                    None
                    if base.get("site_eui_kbtu_ft2_year") is None
                    or final.get("site_eui_kbtu_ft2_year") is None
                    else round(
                        final["site_eui_kbtu_ft2_year"] - base["site_eui_kbtu_ft2_year"],
                        2,
                    )
                ),
            )
            c2.metric(
                "Electricity",
                f"{(final.get('electricity_kwh_year') or 0):,.0f} kWh",
            )
            c3.metric(
                "Gas",
                f"{(final.get('natural_gas_therm_year') or 0):,.0f} therm",
            )
            c4.metric(
                "Utility cost",
                f"${(final.get('utility_cost_usd_year') or 0):,.0f}",
            )

        savings = report.get("savings_by_measure") or []
        if savings:
            st.dataframe(pd.DataFrame(savings), hide_index=True, use_container_width=True)
            fig_w = savings_waterfall_figure(savings)
            if fig_w is not None:
                st.plotly_chart(fig_w, use_container_width=True)
        fig_m = monthly_bar_figure(records)
        if fig_m is not None:
            st.plotly_chart(fig_m, use_container_width=True)
        else:
            st.caption("Monthly series not present in tabular output for this run.")

        art = report.get("artifacts_dir")
        if art:
            st.caption(f"Artifacts: `{art}`")
        with st.expander("Full wattlab_report.json"):
            st.json(report)
