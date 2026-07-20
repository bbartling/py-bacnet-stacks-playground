"""Uploads — wattlab dump v3 + energy-use package dropzone."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from wattlab.energy_use import load_energy_use_package
from wattlab.seed import gap_report, load_bundle
from wattlab.studio.workspace import (
    ensure_workspace,
    list_workspace_summary,
    save_upload_bytes,
    workspace_root,
)


def render() -> None:
    st.header("Uploads — dump + energy use")
    st.caption(
        "Drop a vibe19 **wattlab_dump_*.zip** (v3) and an **energy-use** zip "
        "(campus.json + bill CSVs + optional Haystack column_map). "
        "Chat with Codex/agents on this workspace folder — Studio only displays results."
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
        st.subheader("2 · Energy use (Haystack / campus)")
        energy_up = st.file_uploader(
            "energy-use zip (campus + maps)", type=["zip"], key="uploads_energy_zip"
        )
        energy_path = st.text_input(
            "…or path to campus folder / zip",
            key="uploads_energy_path",
            help="Must contain campus.json and meter CSVs, or Haystack column_map + interval CSVs.",
        )
        if st.button("Load energy use", key="uploads_load_energy"):
            try:
                if energy_up is not None:
                    saved = save_upload_bytes("energy", energy_up.name, energy_up.getvalue())
                    pkg = load_energy_use_package(saved)
                    st.session_state["studio_energy_path"] = str(saved)
                elif energy_path.strip():
                    p = Path(energy_path.strip())
                    if p.is_file() and p.suffix.lower() == ".zip":
                        saved = save_upload_bytes("energy", p.name, p.read_bytes())
                        pkg = load_energy_use_package(saved)
                        st.session_state["studio_energy_path"] = str(saved)
                    else:
                        pkg = load_energy_use_package(p)
                        st.session_state["studio_energy_path"] = str(p)
                else:
                    st.warning("Upload an energy zip or enter a path.")
                    return
                st.session_state["studio_energy"] = pkg
                if pkg.campus is not None:
                    st.session_state["studio_campus"] = pkg.campus
                    st.session_state["fuel_weather_campus"] = pkg.campus
                st.success(
                    f"Energy package loaded"
                    + (f" — campus {pkg.campus.campus_id}" if pkg.campus else "")
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
        missing = [g for g in gaps if g.get("severity") == "required" and g.get("status") == "missing"]
        if missing:
            st.warning(
                "NEEDS_INPUT: "
                + ", ".join(str(g["field"]) for g in missing)
                + " — fill on Twin / calibrate (or via Codex answers.json)."
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
        f"Agent tip: point Codex at `{workspace_root()}` — "
        "uploads/dump, uploads/energy, runs/, reports/."
    )
