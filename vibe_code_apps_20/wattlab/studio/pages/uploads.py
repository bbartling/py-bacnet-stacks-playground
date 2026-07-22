"""Uploads — wattlab dump v3 + energy-use package dropzone."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from wattlab.energy_use import load_energy_use_package
from wattlab.energy_use.excel_campus import campus_to_utility_bills_csv
from wattlab.seed import gap_report, load_bundle
from wattlab.studio.workspace import (
    ensure_workspace,
    list_workspace_summary,
    reports_dir,
    save_upload_bytes,
    workspace_root,
)


def _hints_from_bundle() -> dict[str, Any]:
    """Pull building/area/coords from the loaded dump — data-model, not site hardcodes."""
    bundle = st.session_state.get("studio_bundle")
    out: dict[str, Any] = {}
    if bundle is None:
        return out
    seed = getattr(bundle, "model_seed", None) or {}
    if isinstance(seed, dict):
        area = seed.get("floor_area_ft2")
        if area:
            out["default_area_ft2"] = float(area)
        if seed.get("building_type"):
            out["property_type"] = str(seed["building_type"])
        if seed.get("lat") is not None:
            out["lat"] = float(seed["lat"])
        if seed.get("lon") is not None:
            out["lon"] = float(seed["lon"])
        bid = seed.get("building_id") or getattr(bundle, "building_id", None)
        if bid and area:
            out["building_hints"] = [
                {
                    "building_id": str(bid),
                    "label": str(seed.get("label") or bid),
                    "floor_area_ft2": float(area),
                    "property_type": str(seed.get("building_type") or "office"),
                }
            ]
    return out


def _load_energy(path: Path):
    derive = ensure_workspace() / "uploads" / "energy" / "derived"
    hints = _hints_from_bundle()
    return load_energy_use_package(path, derive_dir=derive, **hints)


def _bridge_utility_bills(pkg: Any) -> None:
    """Write utility_bills.csv for Twin when campus bills exist."""
    campus = getattr(pkg, "campus", None)
    if campus is None or not campus.meters:
        return
    out = reports_dir() / "utility_bills.csv"
    campus_to_utility_bills_csv(campus, out)
    st.session_state["studio_utility_bills_path"] = str(out)
    bundle = st.session_state.get("studio_bundle")
    if bundle is not None:
        try:
            ub = pd.read_csv(out)
            bundle.utility_bills = ub
            st.session_state["studio_bundle"] = bundle
        except Exception:
            pass


def render() -> None:
    st.header("Uploads — dump + energy use")
    st.caption(
        "Drop a vibe19 **wattlab_dump_*.zip** (v3) and an **energy-use** package: "
        "`campus.json` + bill CSVs, Haystack `column_map`, **or** Liberty-style monthly "
        "Excel workbooks (auto-derived to campus). "
        "Chat with any AI agent on this workspace folder — Studio only displays results."
    )

    root = ensure_workspace()
    st.info(f"Workspace: `{root}`")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("1 · WattLab dump (v3)")
        dump_up = st.file_uploader("wattlab_dump_*.zip", type=["zip"], key="uploads_dump_zip")
        dump_path = st.text_input(
            "…or path to dump zip/folder",
            key="uploads_dump_path",
            help="Local path visible to this process (host Studio or bind-mounted /data).",
        )
        if st.button("Load dump", key="uploads_load_dump"):
            try:
                if dump_up is not None:
                    saved = save_upload_bytes("dump", dump_up.name, dump_up.getvalue())
                    bundle = load_bundle(saved)
                    st.session_state["studio_dump_path"] = str(saved)
                elif dump_path.strip():
                    p = Path(dump_path.strip())
                    if p.is_file() and p.suffix.lower() == ".zip":
                        saved = save_upload_bytes("dump", p.name, p.read_bytes())
                        bundle = load_bundle(saved)
                        st.session_state["studio_dump_path"] = str(saved)
                    else:
                        bundle = load_bundle(p)
                        st.session_state["studio_dump_path"] = str(p)
                else:
                    st.warning("Upload a dump zip or enter a path.")
                    return
                st.session_state["studio_bundle"] = bundle
                st.success(f"Dump loaded: {bundle.building_id}")
            except Exception as exc:
                st.error(f"Dump load failed: {exc}")

    with c2:
        st.subheader("2 · Energy use (campus / Excel / Haystack)")
        energy_up = st.file_uploader(
            "energy-use zip", type=["zip"], key="uploads_energy_zip"
        )
        energy_path = st.text_input(
            "…or path to campus folder / zip",
            key="uploads_energy_path",
            help="campus.json + meter CSVs, Excel monthly fuel workbooks, or Haystack maps.",
        )
        if st.button("Load energy use", key="uploads_load_energy"):
            try:
                if energy_up is not None:
                    saved = save_upload_bytes("energy", energy_up.name, energy_up.getvalue())
                    pkg = _load_energy(saved)
                    st.session_state["studio_energy_path"] = str(saved)
                elif energy_path.strip():
                    p = Path(energy_path.strip())
                    if p.is_file() and p.suffix.lower() == ".zip":
                        saved = save_upload_bytes("energy", p.name, p.read_bytes())
                        pkg = _load_energy(saved)
                        st.session_state["studio_energy_path"] = str(saved)
                    else:
                        pkg = _load_energy(p)
                        st.session_state["studio_energy_path"] = str(p)
                else:
                    st.warning("Upload an energy zip or enter a path.")
                    return
                st.session_state["studio_energy"] = pkg
                if pkg.campus is not None:
                    st.session_state["studio_campus"] = pkg.campus
                    st.session_state["fuel_weather_campus"] = pkg.campus
                    _bridge_utility_bills(pkg)

                if getattr(pkg, "fuel_ready", False):
                    msg = f"Energy package ready for Fuel — campus {pkg.campus.campus_id}"
                    if getattr(pkg, "derived_from_excel", False):
                        msg += " (derived from Excel)"
                    st.success(msg)
                else:
                    st.warning(
                        "Energy package loaded but Fuel dashboard is empty — "
                        "need campus.json + bill CSVs or a monthly Excel workbook "
                        "with Month + kWh/Mcf columns."
                    )
                for note in pkg.notes:
                    st.caption(note)
            except Exception as exc:
                st.error(f"Energy load failed: {exc}")

    if st.button("Refresh workspace listing", key="uploads_refresh_ws"):
        st.session_state["studio_ws_summary"] = list_workspace_summary()

    summary = st.session_state.get("studio_ws_summary") or list_workspace_summary()
    st.subheader("Workspace files")
    st.json(summary)

    bundle = st.session_state.get("studio_bundle")
    if bundle is not None:
        s = bundle.summary() if hasattr(bundle, "summary") else {}
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Building", str(s.get("building_id") or getattr(bundle, "building_id", "?")))
        m2.metric("Schema", str(s.get("schema_version") or "—"))
        m3.metric("Tables", str(len(s.get("tables") or {})))
        m4.metric("Bills in dump", "yes" if s.get("has_bills") else "no")
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
            st.warning(
                "NEEDS_INPUT: "
                + ", ".join(str(g["field"]) for g in missing)
                + " — fill on Twin / calibrate (or via agent answers.json)."
            )
        elif answered_via:
            st.info(
                "Dump seed nulls answered via answers.json: "
                + ", ".join(str(g["field"]) for g in answered_via)
                + " — Re-apply bootstrap or Twin form if profile not loaded."
            )
        if bundle.manifest:
            with st.expander("MANIFEST.json", expanded=False):
                st.json(bundle.manifest)

    energy: Any = st.session_state.get("studio_energy")
    if energy is not None and getattr(energy, "campus", None) is not None:
        campus = energy.campus
        st.subheader("Energy campus meters")
        rows = [
            {
                "meter_id": m.meter_id,
                "fuel": m.fuel,
                "unit": m.unit,
                "shared": m.shared,
                "months": len(m.bills),
            }
            for m in campus.meters
        ]
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    st.caption(
        f"Agent tip: point any AI agent at `{workspace_root()}` — "
        "uploads/dump, uploads/energy, runs/, reports/. "
        "Publish Twin sims with publish_run_for_studio so the browser shows 08 panes."
    )
