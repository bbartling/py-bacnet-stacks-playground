"""OpenFDD WattLab Energy Model section for vibe19 Streamlit.

In-app responsive defaults + schedules/ECMs/quick savings via ``app.energy_wizard``.
Optional vibe20 EnergyPlus screening when ``VIBE19_WATTLAB_DIR`` is set
(subprocess only — no cross-imports).
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
        "defaults_ok": False,
        "docker_hint": (
            "Set VIBE19_WATTLAB_DIR to vibe_code_apps_20 and build Docker image "
            "`energyplus-mcp-dev` (see vibe_code_apps_20/third_party/README.md)."
        ),
    }
    if not wattlab:
        return out
    out["easy_button"] = (wattlab / "easy_button.py").is_file()
    out["defaults_ok"] = (wattlab / "defaults" / "archetypes.json").is_file()
    return out


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_form_options(wattlab: Path) -> dict[str, Any]:
    arch_path = wattlab / "defaults" / "archetypes.json"
    clim_path = wattlab / "defaults" / "climate.json"
    codes_path = wattlab / "defaults" / "codes.json"
    if not arch_path.is_file() or not clim_path.is_file() or not codes_path.is_file():
        raise FileNotFoundError(
            f"WattLab defaults missing under {wattlab / 'defaults'} "
            "(need archetypes.json, climate.json, codes.json)."
        )
    arch = _load_json(arch_path)
    clim = _load_json(clim_path)
    codes = _load_json(codes_path)
    sets_path = wattlab / "ecm_library" / "measure_sets.json"
    sets = _load_json(sets_path) if sets_path.is_file() else {}
    building_types = []
    for k, v in arch.items():
        if not isinstance(v, dict) or "label" not in v:
            continue
        building_types.append(
            {
                "id": k,
                "label": v.get("label") or k,
                "default_floors": v.get("default_floors"),
                "default_floor_to_floor_ft": v.get("default_floor_to_floor_ft"),
                "default_wwr": v.get("default_wwr"),
                "default_area_ft2": v.get("default_area_ft2"),
                "hvac_defaults": v.get("hvac_defaults") or {},
                "hvac_options": v.get("hvac_options") or {},
                "extends": v.get("extends"),
            }
        )
        # Merge extends for UI defaults when child omits fields
        if v.get("extends") and v["extends"] in arch:
            base = arch[v["extends"]]
            for field in (
                "default_floors",
                "default_floor_to_floor_ft",
                "default_wwr",
                "default_area_ft2",
                "hvac_defaults",
                "hvac_options",
            ):
                if building_types[-1].get(field) in (None, {}, []):
                    building_types[-1][field] = base.get(field)
    return {
        "building_types": building_types,
        "cities": [
            {
                "id": k,
                "label": v.get("label") or k,
                "climate_zone": v.get("climate_zone") or "",
            }
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
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(wattlab),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        return {
            "ok": False,
            "returncode": -1,
            "stdout": "",
            "stderr": f"Python executable not found: {exc}",
            "report": None,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "returncode": -1,
            "stdout": (exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else "",
            "stderr": f"Timed out after {timeout}s",
            "report": None,
        }
    stdout = proc.stdout or ""
    report = None
    try:
        report = json.loads(stdout)
    except json.JSONDecodeError:
        start = stdout.rfind("\n{")
        if start < 0:
            start = stdout.find("{")
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
        # Avoid fragile quoting: pass path as argv via a tiny driver script file
        driver = tmp.with_suffix(".py")
        driver.write_text(
            "import json,sys\n"
            "from wattlab_defaults import resolve_profile\n"
            f"print(json.dumps(resolve_profile(json.load(open({str(tmp)!r}, encoding='utf-8')))))\n",
            encoding="utf-8",
        )
        try:
            return _run_python(wattlab, [str(driver)], timeout=60)
        finally:
            driver.unlink(missing_ok=True)
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
    if batch_results and results_summary_fn:
        summary = results_summary_fn(batch_results)
        if isinstance(summary, pd.DataFrame):
            summary.to_csv(out_dir / "fdd_summary.csv", index=False)
        else:
            pd.DataFrame(summary).to_csv(out_dir / "fdd_summary.csv", index=False)
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


def run_calibrate(
    wattlab: Path,
    bundle_dir: Path,
    *,
    dry_run: bool = False,
    lat: float | None = None,
    lon: float | None = None,
    timeout: int = 1800,
) -> dict[str, Any]:
    args = ["calibrate.py", "--bundle", str(bundle_dir)]
    if dry_run:
        args.append("--dry-run")
    if lat is not None:
        args.extend(["--lat", str(lat)])
    if lon is not None:
        args.extend(["--lon", str(lon)])
    return _run_python(wattlab, args, timeout=timeout)


def default_utility_bills_rows() -> list[dict[str, Any]]:
    return [{"month": m, "kwh": None, "therms": None} for m in range(1, 13)]


def signature_overlay_figure(scorecard: dict[str, Any], *, kind: str = "fan"):
    """Observed vs simulated on-fraction by OAT bin."""
    import plotly.graph_objects as go

    block = ((scorecard.get("signatures") or {}).get(kind)) or {}
    per_bin = block.get("per_bin") or []
    if not per_bin:
        return None
    bins = [r["bin_start"] for r in per_bin]
    obs = [r["observed_on_fraction"] for r in per_bin]
    sim = [r["simulated_on_fraction"] for r in per_bin]
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Observed", x=bins, y=obs, marker_color="#4C78A8"))
    fig.add_trace(go.Bar(name="Simulated", x=bins, y=sim, marker_color="#F58518"))
    fig.update_layout(
        barmode="group",
        title=f"{kind} on-fraction by OAT bin (overlap window)",
        xaxis_title="OAT bin start (°F)",
        yaxis_title="On fraction",
        height=360,
        margin=dict(t=50, b=40),
    )
    return fig


def bills_overlay_figure(scorecard: dict[str, Any]):
    import plotly.graph_objects as go

    block = scorecard.get("utility_bills") or {}
    per = block.get("per_month") or []
    if not per:
        return None
    months = [r["month"] for r in per]
    obs = [r["observed_kwh"] for r in per]
    sim = [r["simulated_kwh"] for r in per]
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Bills kWh", x=months, y=obs, marker_color="#4C78A8"))
    fig.add_trace(go.Bar(name="Simulated kWh", x=months, y=sim, marker_color="#F58518"))
    fig.update_layout(
        barmode="group",
        title="Monthly electricity — bills vs simulated",
        xaxis_title="Month",
        yaxis_title="kWh",
        height=360,
        margin=dict(t=50, b=40),
    )
    return fig


def write_model_seed_bundle(
    out_dir: Path,
    *,
    frames: dict[str, Any],
    role_map: dict,
    weather: Any,
    building_id: str,
    minimal: dict[str, Any],
    utility_bills: list[dict[str, Any]] | None = None,
    lat: float | None = None,
    lon: float | None = None,
) -> Path:
    """Write a vibe19 model-seed bundle for WattLab calibrate.py."""
    from app.model_seed import build_model_seed_dict, infer_schedules, operating_signatures

    out_dir.mkdir(parents=True, exist_ok=True)
    sched_table, sched_payload = infer_schedules(frames, role_map)
    signatures = operating_signatures(frames, role_map, weather=weather)
    sched_table.to_csv(out_dir / "schedule_inference_table.csv", index=False)
    (out_dir / "schedule_inference.json").write_text(
        json.dumps(sched_payload, indent=2, default=str), encoding="utf-8"
    )
    signatures.to_csv(out_dir / "operating_signatures.csv", index=False)
    if weather is not None and isinstance(weather, pd.DataFrame) and not weather.empty:
        wx = weather.copy()
        if isinstance(wx.index, pd.DatetimeIndex):
            wx = wx.reset_index()
            first = wx.columns[0]
            if first != "timestamp_utc":
                wx = wx.rename(columns={first: "timestamp_utc"})
        wx.to_csv(out_dir / "weather_observed.csv", index=False)

    bills = []
    if utility_bills:
        for r in utility_bills:
            if r.get("kwh") is None and r.get("therms") is None:
                continue
            bills.append(
                {
                    "month": int(r["month"]),
                    "kwh": r.get("kwh"),
                    "therms": r.get("therms"),
                }
            )
        if bills:
            pd.DataFrame(bills).to_csv(out_dir / "utility_bills.csv", index=False)

    seed = build_model_seed_dict(
        building_id=building_id or "unknown",
        schedule_payload=sched_payload,
        signatures=signatures,
        city=minimal.get("city"),
        lat=lat,
        lon=lon,
        utility_bills=bills or None,
        extras={
            "building_type": minimal.get("building_type"),
            "floor_area_ft2": minimal.get("floor_area_ft2"),
            "floors": minimal.get("floors"),
            "floor_to_floor_ft": minimal.get("floor_to_floor_ft"),
            "wwr": minimal.get("wwr"),
            "hvac": minimal.get("hvac"),
            "utility": minimal.get("utility"),
            "code_year": minimal.get("code_year"),
            "anonymized": True,
        },
    )
    # User geometry overrides the null placeholders
    if minimal.get("building_type"):
        seed["building_type"] = minimal["building_type"]
        seed["field_sources"]["building_type"] = {"source": "user"}
    if minimal.get("floor_area_ft2"):
        seed["floor_area_ft2"] = minimal["floor_area_ft2"]
        seed["field_sources"]["floor_area_ft2"] = {"source": "user"}
    if minimal.get("floors"):
        seed["floors"] = minimal["floors"]
    (out_dir / "model_seed.json").write_text(
        json.dumps(seed, indent=2, default=str), encoding="utf-8"
    )
    (out_dir / "run_report.json").write_text(
        json.dumps({"building_id": building_id, "product": "OpenFDD Model Seed"}, indent=2),
        encoding="utf-8",
    )
    return out_dir


def flatten_savings_rows(savings: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for s in savings:
        vb = s.get("vs_baseline") or {}
        vp = s.get("vs_previous") or {}
        rows.append(
            {
                "step": s.get("step"),
                "measure_id": s.get("measure_id"),
                "electricity_kwh_year": s.get("electricity_kwh_year"),
                "natural_gas_therm_year": s.get("natural_gas_therm_year"),
                "site_eui_kbtu_ft2_year": s.get("site_eui_kbtu_ft2_year"),
                "utility_cost_usd_year": s.get("utility_cost_usd_year"),
                "kwh_saved_vs_baseline": vb.get("kwh_saved"),
                "kwh_pct_vs_baseline": vb.get("kwh_pct"),
                "cost_saved_vs_baseline": vb.get("cost_saved_usd"),
                "kwh_saved_vs_previous": vp.get("kwh_saved"),
            }
        )
    return pd.DataFrame(rows)


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
    floor_area = max(float(area_ft2), 1.0) / floors
    width = math.sqrt(floor_area / max(aspect_ratio, 0.1))
    length = floor_area / max(width, 0.1)
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

    L = float(dims["length_ft"])
    W = float(dims["width_ft"])
    H = float(dims["height_ft"])
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
    n_floors = max(1, int(dims["floors"]))
    for f in range(1, n_floors):
        zf = f * (H / n_floors)
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
        title=(
            f"Conceptual massing · WWR {dims['wwr']:.0%} · "
            f"{dims['gross_area_ft2']:,.0f} ft²"
        ),
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


def savings_bar_figure(savings: list[dict[str, Any]]):
    import plotly.graph_objects as go

    if not savings:
        return None
    labels = [str(r.get("measure_id") or f"step{i}") for i, r in enumerate(savings)]
    y = []
    for r in savings:
        vb = (r.get("vs_baseline") or {}).get("kwh_saved")
        y.append(float(vb) if vb is not None else 0.0)
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


def _sync_geometry_defaults(btype: str, arch: dict[str, Any]) -> None:
    """When building type changes, refresh geometry + HVAC widget session state."""
    hvac_def = arch.get("hvac_defaults") or {}
    if st.session_state.get("_em_btype") != btype:
        st.session_state["_em_btype"] = btype
        st.session_state["em_area"] = float(arch.get("default_area_ft2") or 50000)
        st.session_state["em_floors"] = int(arch.get("default_floors") or 3)
        st.session_state["em_ftf"] = float(arch.get("default_floor_to_floor_ft") or 13.0)
        st.session_state["em_wwr"] = float(arch.get("default_wwr") or 0.33)
        # Reset HVAC keyed selectboxes so prior values can't fall outside new options
        for key in ("em_fuel", "em_airside", "em_plant", "em_doas"):
            st.session_state.pop(key, None)
        if hvac_def.get("fuel"):
            st.session_state["em_fuel"] = hvac_def["fuel"]
        if hvac_def.get("airside"):
            st.session_state["em_airside"] = hvac_def["airside"]
        if hvac_def.get("plant"):
            st.session_state["em_plant"] = hvac_def["plant"]
        if hvac_def.get("doas"):
            st.session_state["em_doas"] = hvac_def["doas"]
    st.session_state.setdefault("em_area", float(arch.get("default_area_ft2") or 50000))
    st.session_state.setdefault("em_floors", int(arch.get("default_floors") or 3))
    st.session_state.setdefault("em_ftf", float(arch.get("default_floor_to_floor_ft") or 13.0))
    st.session_state.setdefault("em_wwr", float(arch.get("default_wwr") or 0.33))
    if (arch.get("hvac_defaults") or {}).get("doas"):
        st.session_state.setdefault("em_doas", arch["hvac_defaults"]["doas"])
    else:
        st.session_state.setdefault("em_doas", "none")


# ---------------------------------------------------------------------------
# Streamlit render
# ---------------------------------------------------------------------------


def render_energy_model_tab(
    *,
    batch_results: list | None = None,
    results_summary_fn=None,
    frames: dict | None = None,
    role_map: dict | None = None,
    weather: pd.DataFrame | None = None,
) -> None:
    """In-app easy-button Energy Model — works without vibe20; EP sidecar optional."""
    from app.energy_wizard import (
        attach_quick_estimates,
        form_options,
        resolve_profile,
        schedules_from_inference,
        suggest_measures_from_fdd,
        write_energy_model_package,
    )
    from app.model_seed import infer_schedules, operating_signatures

    st.subheader("Energy Model · OpenFDD WattLab")
    st.caption(
        "Easy-button energy screen: enter what you know (type, area, city, HVAC). "
        "Everything else uses **responsive defaults** with provenance (default / user / data-derived). "
        "EnergyPlus **autosizes** capacities — fan sizes and plant tons are not required. "
        "Export a package for an outside AI agent + EnergyPlus-MCP; optional vibe20 Docker screening when available."
    )

    options = form_options()
    wattlab = resolve_wattlab_dir()
    status = wattlab_status(wattlab)
    if wattlab and status.get("easy_button"):
        st.success(f"EnergyPlus sidecar ready · `{wattlab}`")
    else:
        st.info(
            "In-app wizard is fully available. EnergyPlus screening/calibration is optional — "
            "set **VIBE19_WATTLAB_DIR** to vibe_code_apps_20 and build `energyplus-mcp-dev` when you want live sims."
        )

    # --- Infer schedules from loaded package ---
    schedule_payload = None
    sig_df = pd.DataFrame()
    data_span_h = 0.0
    fan_hours = 0.0
    if frames:
        try:
            _sched_df, schedule_payload = infer_schedules(frames, role_map or {})
            sig_df = operating_signatures(frames, role_map or {}, weather=weather)
            # span from first equipment index
            for _eq, df in frames.items():
                if isinstance(df.index, pd.DatetimeIndex) and len(df.index) >= 2:
                    data_span_h = max(
                        data_span_h,
                        (df.index.max() - df.index.min()).total_seconds() / 3600.0,
                    )
            for _eq_id, row in (schedule_payload.get("equipment") or {}).items():
                if isinstance(row, dict) and row.get("on_samples") and row.get("poll_seconds"):
                    fan_hours += float(row["on_samples"]) * float(row["poll_seconds"]) / 3600.0
        except Exception as exc:
            st.caption(f"Schedule inference skipped: {exc}")
            schedule_payload = None

    with st.expander("Building inputs (easy button)", expanded=True):
        c1, c2, c3 = st.columns(3)
        type_ids = [t["id"] for t in options["building_types"]]
        type_labels = {t["id"]: t["label"] for t in options["building_types"]}
        btype = c1.selectbox(
            "Building type",
            type_ids,
            format_func=lambda i: type_labels.get(i, i),
            index=type_ids.index("office") if "office" in type_ids else 0,
            key="em_btype_select",
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
            key="em_city_select",
        )
        code_ids = [c["id"] for c in options["codes"]]
        code_labels = {c["id"]: c["label"] for c in options["codes"]}
        default_code = options.get("default_code") or code_ids[0]
        code = c3.selectbox(
            "Energy code vintage",
            code_ids,
            format_func=lambda i: code_labels.get(i, i),
            index=code_ids.index(default_code) if default_code in code_ids else 0,
            key="em_code_select",
        )

        arch = next((t for t in options["building_types"] if t["id"] == btype), {})
        _sync_geometry_defaults(btype, arch)

        d1, d2, d3, d4 = st.columns(4)
        area = d1.number_input("Gross floor area (ft²)", min_value=1000.0, step=1000.0, key="em_area")
        floors = d2.number_input("Floors", min_value=1, step=1, key="em_floors")
        ftf = d3.number_input("Floor-to-floor (ft)", min_value=8.0, step=0.5, key="em_ftf")
        wwr = d4.number_input("Window-to-wall ratio", min_value=0.0, max_value=0.9, step=0.01, key="em_wwr")

        hvac_opts = arch.get("hvac_options") or {}
        h1, h2, h3, h4 = st.columns(4)
        fuel_opts = hvac_opts.get("fuel") or ["gas", "electric"]
        air_opts = hvac_opts.get("airside") or ["vav_reheat"]
        plant_opts = hvac_opts.get("plant") or ["air_cooled_chiller"]
        doas_opts = hvac_opts.get("doas") or ["none"]
        fuel = h1.selectbox("Heating fuel", fuel_opts, key="em_fuel")
        airside = h2.selectbox("Air-side system", air_opts, key="em_airside")
        plant = h3.selectbox("Cooling / plant", plant_opts, key="em_plant")
        doas = h4.selectbox("DOAS", doas_opts, key="em_doas")

        u1, u2, u3 = st.columns(3)
        st.session_state.setdefault("em_elec", 0.09)
        st.session_state.setdefault("em_gas", 0.693)
        elec = u1.number_input("Electricity ($/kWh)", min_value=0.01, step=0.01, key="em_elec")
        gas = u2.number_input("Natural gas ($/therm)", min_value=0.01, step=0.01, key="em_gas")
        set_ids = [s["id"] for s in options["measure_sets"]] or ["good", "better", "best"]
        measure_set = u3.selectbox(
            "Measure set",
            set_ids,
            index=set_ids.index("best") if "best" in set_ids else 0,
            key="em_measure_set",
        )

        fig = massing_figure(
            rectangular_massing(float(area), int(floors), float(ftf), float(wwr), aspect_ratio=1.5)
        )
        if fig is not None:
            st.plotly_chart(fig, width="stretch", key="em_massing")

    # Schedules
    _, arch_full = __import__("app.energy_wizard", fromlist=["resolve_building_type"]).resolve_building_type(btype)
    sched = schedules_from_inference(schedule_payload, arch=arch_full)
    with st.expander("Schedules (prefilled from data when available)", expanded=bool(sched.get("from_inference"))):
        src = sched.get("source") or "default"
        st.caption(f"Source: **{src}**" + (f" · signal `{sched.get('inference_signal')}`" if sched.get("inference_signal") else ""))
        s1, s2, s3, s4 = st.columns(4)
        wd_s = s1.number_input("Weekday start hour", 0, 24, int(sched["weekday_start_hour"]), key="em_wd_start")
        wd_e = s2.number_input("Weekday stop hour", 0, 24, int(sched["weekday_stop_hour"]), key="em_wd_stop")
        we_s = s3.number_input("Weekend start hour", 0, 24, int(sched["weekend_start_hour"]), key="em_we_start")
        we_e = s4.number_input("Weekend stop hour", 0, 24, int(sched["weekend_stop_hour"]), key="em_we_stop")
        t1, t2, t3, t4 = st.columns(4)
        cool_occ = t1.number_input("Cool occupied °F", value=float(sched["cool_occupied_f"]), key="em_cool_occ")
        cool_un = t2.number_input("Cool unoccupied °F", value=float(sched["cool_unoccupied_f"]), key="em_cool_un")
        heat_occ = t3.number_input("Heat occupied °F", value=float(sched["heat_occupied_f"]), key="em_heat_occ")
        heat_un = t4.number_input("Heat unoccupied °F", value=float(sched["heat_unoccupied_f"]), key="em_heat_un")
        # Rebuild hourly blocks from edited hours
        from app.energy_wizard import _hourly_block

        sched["weekday_start_hour"] = int(wd_s)
        sched["weekday_stop_hour"] = int(wd_e)
        sched["weekend_start_hour"] = int(we_s)
        sched["weekend_stop_hour"] = int(we_e)
        sched["cool_occupied_f"] = float(cool_occ)
        sched["cool_unoccupied_f"] = float(cool_un)
        sched["heat_occupied_f"] = float(heat_occ)
        sched["heat_unoccupied_f"] = float(heat_un)
        occ_wd = _hourly_block(int(wd_s), int(wd_e))
        occ_we = _hourly_block(int(we_s), int(we_e))
        sched["weekday"]["occupancy"] = occ_wd
        sched["weekday"]["ventilation"] = list(occ_wd)
        sched["weekday"]["lighting"] = list(occ_wd)
        sched["weekend"]["occupancy"] = occ_we
        sched["weekend"]["ventilation"] = list(occ_we)
        sched["weekend"]["lighting"] = list(occ_we)
        st.dataframe(
            pd.DataFrame({"hour": list(range(24)), "weekday_occ": occ_wd, "weekend_occ": occ_we}),
            hide_index=True,
            width="stretch",
            height=220,
        )

    # Advanced envelope / loads (collapsed)
    with st.expander("Advanced · envelope, loads, HVAC efficiencies", expanded=False):
        preview = resolve_profile(
            {
                "building_type": btype,
                "city": city,
                "code_year": code,
                "floor_area_ft2": float(area),
                "floors": int(floors),
            }
        )
        env = preview.get("envelope") or {}
        e1, e2, e3, e4 = st.columns(4)
        roof_u = e1.number_input("Roof U", value=float(env.get("roof_u") or 0.032), format="%.3f", key="em_roof_u")
        wall_u = e2.number_input("Wall U", value=float(env.get("wall_u") or 0.064), format="%.3f", key="em_wall_u")
        glaz_u = e3.number_input("Glazing U", value=float(env.get("glazing_u") or 0.38), format="%.3f", key="em_glaz_u")
        shgc = e4.number_input("SHGC", value=float(env.get("glazing_shgc") or 0.38), format="%.2f", key="em_shgc")
        l1, l2, l3, l4 = st.columns(4)
        loads = preview.get("loads") or {}
        equip = preview.get("equipment") or {}
        lpd = l1.number_input("LPD W/ft²", value=float(loads.get("lpd_w_per_ft2") or 0.7), key="em_lpd")
        plug = l2.number_input("Plug W/ft²", value=float(loads.get("plug_w_per_ft2") or 0.75), key="em_plug")
        fan_w = l3.number_input("Fan W/CFM", value=float(equip.get("fan_w_per_cfm") or 1.1), key="em_fan_w")
        eer = l4.number_input("Cooling EER", value=float(equip.get("cooling_eer") or 9.8), key="em_eer")
        st.caption("Field sources (provenance):")
        src_rows = [
            {"field": k, "value": str(v.get("value")), "source": v.get("source")}
            for k, v in (preview.get("field_sources") or {}).items()
        ]
        if src_rows:
            st.dataframe(pd.DataFrame(src_rows).head(30), hide_index=True, width="stretch", height=200)

    # Build profile
    minimal = {
        "project_id": st.session_state.get("building_id") or f"WATTLAB-{btype.upper()}",
        "building_type": btype,
        "city": city,
        "code_year": code,
        "floor_area_ft2": float(area),
        "floors": int(floors),
        "floor_to_floor_ft": float(ftf),
        "wwr": float(wwr),
        "hvac": {"fuel": fuel, "airside": airside, "plant": plant, "doas": doas},
        "utility": {"elec_usd_per_kwh": float(elec), "gas_usd_per_therm": float(gas)},
        "measure_set": measure_set,
        "schedules": sched,
        "lpd_w_per_ft2": float(st.session_state.get("em_lpd") or 0.7),
        "plug_w_per_ft2": float(st.session_state.get("em_plug") or 0.75),
        "fan_w_per_cfm": float(st.session_state.get("em_fan_w") or 1.1),
        "cooling_eer": float(st.session_state.get("em_eer") or 9.8),
        "envelope": {
            "roof_u": float(st.session_state.get("em_roof_u", 0.032)),
            "wall_u": float(st.session_state.get("em_wall_u", 0.064)),
            "glazing_u": float(st.session_state.get("em_glaz_u", 0.38)),
            "glazing_shgc": float(st.session_state.get("em_shgc", 0.38)),
        },
    }
    profile = resolve_profile(minimal)
    st.session_state["wattlab_resolved_profile"] = profile

    # ECM prefill + quick savings
    summary = None
    if results_summary_fn and batch_results:
        try:
            summary = results_summary_fn(batch_results)
        except Exception:
            summary = None
    measures = suggest_measures_from_fdd(
        batch_results=batch_results, results_summary=summary, measure_set=measure_set
    )

    # Evidence for estimators
    prohibited = 0.0
    duct_mean = None
    try:
        from app.analytics import economizer_weather_summary, motor_run_hours_table

        if frames:
            eco = economizer_weather_summary(frames, role_map or {}, weather=weather)
            if eco is not None and not eco.empty and "prohibited_mech_hours_below_60f" in eco.columns:
                prohibited = float(eco["prohibited_mech_hours_below_60f"].sum())
            mtab = motor_run_hours_table(frames, role_map or {})
            if mtab is not None and not mtab.empty and "run_hours" in mtab.columns:
                if "motor_kind" in mtab.columns:
                    fan_mask = mtab["motor_kind"].astype(str).str.lower().eq("fan")
                    fan_hours = float(mtab.loc[fan_mask, "run_hours"].sum()) if fan_mask.any() else float(mtab["run_hours"].sum())
                else:
                    fan_hours = float(mtab["run_hours"].sum())
            # duct static from signatures / role
            for eq_id, raw in (frames or {}).items():
                from app.role_map import apply_role_map

                mapped = apply_role_map(raw, eq_id, role_map or {})
                if "duct-static-pressure" in mapped.columns and mapped["duct-static-pressure"].notna().any():
                    duct_mean = float(pd.to_numeric(mapped["duct-static-pressure"], errors="coerce").mean())
                    break
    except Exception:
        pass

    measures = attach_quick_estimates(
        measures,
        fan_run_hours=fan_hours,
        data_span_hours=data_span_h or 1.0,
        duct_static_mean_iwc=duct_mean,
        prohibited_mech_hours=prohibited,
        schedules=sched,
        elec_usd_per_kwh=float(elec),
        fan_kw=float(st.session_state.get("em_fan_kw_assume", 15.0)),
        plant_kw=float(st.session_state.get("em_plant_kw_assume", 40.0)),
    )
    profile["measures"] = measures

    st.markdown("##### Recommended measures + quick savings estimates")
    st.caption(
        "Screening-grade bin-hour / affinity estimates from your FDD data — **not** EnergyPlus results. "
        "Toggle measures into the export package for the outside modeling agent."
    )
    enabled_ids: list[str] = []
    for m in measures:
        mid = m.get("measure_id") or ""
        title = m.get("title") or mid
        qe = m.get("quick_estimate") or {}
        label = f"{mid} — {title}"
        on = st.checkbox(label, value=bool(m.get("enabled", True)), key=f"em_meas_{mid}")
        if on:
            enabled_ids.append(mid)
            m["enabled"] = True
        else:
            m["enabled"] = False
        if qe.get("status") == "ok":
            st.caption(
                f"  → ~{qe.get('kwh_savings', 0):,.0f} kWh / ${qe.get('usd_savings', 0):,.0f} "
                f"({qe.get('estimator')}) · {qe.get('notes', '')}"
            )
        elif qe.get("status") == "skipped":
            st.caption(f"  → estimate skipped: {qe.get('reason')}")

    profile["measures"] = [m for m in measures if m.get("enabled")]
    quick_summary = {
        "total_kwh": sum((m.get("quick_estimate") or {}).get("kwh_savings") or 0 for m in profile["measures"]),
        "total_usd": sum((m.get("quick_estimate") or {}).get("usd_savings") or 0 for m in profile["measures"]),
        "measures": [
            {
                "measure_id": m.get("measure_id"),
                "kwh": (m.get("quick_estimate") or {}).get("kwh_savings"),
                "usd": (m.get("quick_estimate") or {}).get("usd_savings"),
                "estimator": (m.get("quick_estimate") or {}).get("estimator"),
            }
            for m in profile["measures"]
        ],
    }
    m1, m2 = st.columns(2)
    m1.metric("Quick kWh savings (screening)", f"{quick_summary['total_kwh']:,.0f}")
    m2.metric("Quick $ savings (screening)", f"${quick_summary['total_usd']:,.0f}")

    # Export package
    st.markdown("##### Export Energy Model Package")
    if st.button("Build export package (for AI agent + EnergyPlus)", type="primary", key="em_export_pkg"):
        import tempfile

        out = Path(tempfile.mkdtemp(prefix="wattlab_pkg_"))
        zpath = write_energy_model_package(
            out,
            profile=profile,
            schedules=sched,
            measures=profile["measures"],
            schedule_inference=schedule_payload,
            operating_signatures=sig_df if sig_df is not None else None,
            weather=weather,
            quick_savings_summary=quick_summary,
        )
        st.session_state["em_export_zip"] = str(zpath)
        st.success(f"Package written · `{zpath}`")
    zpath = st.session_state.get("em_export_zip")
    if zpath and Path(zpath).is_file():
        st.download_button(
            "Download energy_model_package.zip",
            data=Path(zpath).read_bytes(),
            file_name="energy_model_package.zip",
            mime="application/zip",
            key="em_dl_pkg",
        )

    # Optional vibe20 EnergyPlus screening
    if wattlab and status.get("easy_button"):
        st.markdown("##### Optional · live EnergyPlus screening (vibe20 sidecar)")
        r1, r2, r3 = st.columns(3)
        run_baseline = r1.button("Run baseline only", key="wattlab_run_base")
        run_set = r2.button(f"Run baseline + {measure_set}", key="wattlab_run_set")
        run_dry = r3.button("Dry-run plan", key="wattlab_dry")
        if run_dry or run_baseline or run_set:
            try:
                use_set = None if run_baseline else measure_set
                run_profile = dict(profile)
                if run_baseline:
                    run_profile["measures"] = []
                with st.spinner("Calling vibe20 easy_button…"):
                    out = run_easy_button(
                        wattlab,
                        profile=run_profile,
                        measure_set=use_set,
                        dry_run=bool(run_dry),
                    )
                if out.get("report") is not None:
                    st.session_state["wattlab_last_report"] = out["report"]
                if not out.get("ok") and not run_dry:
                    st.warning("EnergyPlus run reported a non-zero exit.")
                    st.code(out.get("stderr") or out.get("stdout") or "")
            except Exception as exc:
                st.exception(exc)

        report = st.session_state.get("wattlab_last_report")
        if report:
            st.markdown("##### EnergyPlus results")
            if report.get("dry_run"):
                st.json(report)
            else:
                records = report.get("result_records") or []
                if records:
                    final = records[-1].get("annual") or {}
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Site EUI", f"{final.get('site_eui_kbtu_ft2_year') or '—'} kBtu/ft²")
                    c2.metric("Electricity", f"{(final.get('electricity_kwh_year') or 0):,.0f} kWh")
                    c3.metric("Gas", f"{(final.get('natural_gas_therm_year') or 0):,.0f} therm")
                    c4.metric("Utility cost", f"${(final.get('utility_cost_usd_year') or 0):,.0f}")
                savings = report.get("savings_by_measure") or []
                if savings:
                    st.dataframe(flatten_savings_rows(savings), hide_index=True, width="stretch")
                    fig_w = savings_bar_figure(savings)
                    if fig_w is not None:
                        st.plotly_chart(fig_w, width="stretch")
                with st.expander("Full wattlab_report.json"):
                    st.json(report)

    with st.expander("Resolved building_profile.json", expanded=False):
        st.json(profile)

