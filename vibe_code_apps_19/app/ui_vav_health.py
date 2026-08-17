"""Overview VAV health matrix — Streamlit rendering only."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from app.vav_health import compute_vav_health_matrix, provenance_caption

_GROUP_ORDER = (
    ("3/3", "3/3 — all three dimensions"),
    ("2/3", "2/3"),
    ("1/3", "1/3"),
    ("0/3", "0/3"),
    ("?/3", "Insufficient evidence"),
)


def _tri_label(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "unknown"
    if pd.isna(value):
        return "unknown"
    return "yes" if bool(value) else "no"


def _display_table(part: pd.DataFrame) -> pd.DataFrame:
    if part.empty:
        return pd.DataFrame(columns=["VAV", "Broken box", "Poor comfort", "Rogue damper", "Score"])
    return pd.DataFrame(
        {
            "VAV": part["equipment_id"].astype(str),
            "Broken box": part["broken_box"].map(_tri_label),
            "Poor comfort": part["poor_zone_performance"].map(_tri_label),
            "Rogue damper": part["rogue_damper"].map(_tri_label),
            "Score": part["score_label"].astype(str),
        }
    )


def render_vav_health_overview() -> None:
    st.markdown("##### VAV health — broken boxes, comfort, and rogue zones.")
    st.caption(
        "This is a **cohort triage** view. A full-open damper can mean airflow starvation, "
        "high load, bad calibration, unreachable setpoint, or actuator trouble — it is not "
        "by itself proof of a failed actuator. Unknown evidence is shown as unknown, never PASS."
    )
    frames = st.session_state.get("equipment_frames") or {}
    batch = st.session_state.get("batch_results") or []
    if not batch:
        st.info(
            "Run all rules (sidebar or Run Rules) so the broken-box dimension can use "
            "complete cookbook results. Comfort and rogue-damper still use mapped timeseries."
        )
    try:
        matrix, summary, cfg = compute_vav_health_matrix(
            frames,
            building_id=str(st.session_state.get("building_id") or "HVAC_BUILDING"),
            batch_results=batch,
            occupancy=st.session_state.get("occupancy_schedule"),
            role_map=st.session_state.get("role_map") or {},
            parent_ahu=st.session_state.get("vav_to_ahu")
            or (st.session_state.get("package_report") or {}).get("vav_to_ahu"),
            zone_lo_f=float(st.session_state.get("zone_lo_f", 70.0)),
            zone_hi_f=float(st.session_state.get("zone_hi_f", 75.0)),
        )
    except Exception as exc:
        st.warning(f"VAV health matrix unavailable: {exc}")
        return

    groups = summary.get("groups") or {}
    n3 = int((groups.get("3/3") or {}).get("count") or 0)
    n2 = int((groups.get("2/3") or {}).get("count") or 0)
    n1 = int((groups.get("1/3") or {}).get("count") or 0)
    n0 = int((groups.get("0/3") or {}).get("count") or 0)
    nq = int((groups.get("?/3") or {}).get("count") or 0)
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Meet all 3", n3)
    m2.metric("Meet 2", n2)
    m3.metric("Meet 1", n1)
    m4.metric("Meet 0", n0)
    m5.metric("Insufficient evidence", nq)

    if matrix.empty:
        st.info("No VAV/zone equipment in the loaded frames.")
        st.caption(provenance_caption(cfg))
        return

    for label, heading in _GROUP_ORDER:
        part = matrix.loc[matrix["score_label"] == label]
        with st.expander(f"{heading} ({len(part)})", expanded=label in {"3/3", "?/3"}):
            st.dataframe(_display_table(part), width="stretch", hide_index=True)

    st.caption(provenance_caption(cfg))
