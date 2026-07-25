"""Streamlit helpers for Engineering Findings Report downloads."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

from app.docx_report import load_generic_rcx_report, report_path

MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def report_download_button(
    filename: str,
    label: str,
    key: str,
    *,
    primary: bool = False,
    help: str | None = None,
    use_container_width: bool = True,
) -> bool:
    """Render a download button for a file under ``assets/reports``. Returns True if shown."""
    path = report_path(filename)
    if not path.is_file():
        st.warning(f"Report template is not available: `{filename}`")
        return False
    st.download_button(
        label=label,
        data=path.read_bytes(),
        file_name=filename,
        mime=MIME_DOCX,
        key=key,
        type="primary" if primary else "secondary",
        help=help or f"Serves `{filename}` from assets/reports.",
        use_container_width=use_container_width,
    )
    return True


def overview_context_from_session() -> dict[str, Any]:
    """Build overview_context from Streamlit session for Engineering Findings charts."""
    from app.analytics import dataset_time_span
    from app.occupancy import OccupancySchedule, occupied_hours_per_week
    from app.reporting.overview_export import build_overview_context

    frames = st.session_state.get("equipment_frames") or {}
    span = dataset_time_span(frames) if frames else {}
    oat_err = 5.0
    try:
        oat_err = float(
            (st.session_state.get("params") or {}).get("OAT-METEO", {}).get("oat_err", 5.0)
        )
    except (TypeError, ValueError):
        oat_err = 5.0
    sched = OccupancySchedule.from_dict(st.session_state.get("occupancy_schedule"))
    return build_overview_context(
        frames=frames,
        role_map=st.session_state.get("role_map") or {},
        weather=st.session_state.get("weather"),
        prefer_web_oat=bool(st.session_state.get("prefer_web_oat", True)),
        oat_err=oat_err,
        chw_leave_max_f=float(st.session_state.get("chw_leave_max_f", 48.0)),
        use_status_proof=bool(
            st.session_state.get("use_mech_cooling_status_proof", True)
        ),
        zone_lo_f=float(st.session_state.get("zone_lo_f", 70.0)),
        zone_hi_f=float(st.session_state.get("zone_hi_f", 75.0)),
        bare_min_occ_hours=float(occupied_hours_per_week(sched)),
        occupancy_schedule=sched.to_dict(),
        dataset_start=span.get("start"),
        dataset_end=span.get("end"),
        span_hours=span.get("span_hours"),
    )


def render_engineering_findings_panel(
    *,
    batch_results: list | None = None,
    building_name: str = "",
    analysis_period: str = "",
    overview_context: dict[str, Any] | None = None,
    key_prefix: str = "eng_findings",
) -> None:
    """Generate FDD Engineering Findings Report (button-triggered; never on section visit)."""
    st.markdown("##### Reports")
    st.markdown("**FDD Engineering Findings Report** (evidence-reviewed)")
    st.caption(
        "Performs an automated evidence review of FDD/RCx rule results before presenting "
        "prioritized findings. Findings remain advisory and should be field-verified. "
        "Detection ≠ finding — raw rule hits and likely false positives stay in the appendices."
    )
    if not batch_results:
        st.info("Run rules above first so FAULT rows are available for evidence review.")
        return

    if st.button(
        "Generate FDD Engineering Findings Report",
        key=f"{key_prefix}_generate",
        type="primary",
    ):
        try:
            import docx  # noqa: F401
        except ImportError:
            st.error(
                "python-docx is missing from this image. Rebuild/pull a tip that includes "
                "engineering-report extras (`python-docx`, `kaleido`)."
            )
            return
        with st.spinner("Evidence review + charts…"):
            try:
                from app.reporting.pipeline import (
                    build_engineering_findings,
                    render_engineering_report,
                )

                ctx = overview_context
                if ctx is None:
                    try:
                        ctx = overview_context_from_session()
                    except Exception:
                        ctx = None
                art = build_engineering_findings(
                    building=building_name or "Building",
                    analysis_period=analysis_period,
                    rule_results=list(batch_results),
                    overview_context=ctx,
                )
                buf_dir = Path(
                    st.session_state.get("_eng_findings_tmpdir")
                    or "/tmp/vibe19_eng_findings"
                )
                buf_dir.mkdir(parents=True, exist_ok=True)
                st.session_state["_eng_findings_tmpdir"] = str(buf_dir)
                written = render_engineering_report(
                    art,
                    buf_dir,
                    docx=True,
                    json_out=True,
                    charts=True,
                    overview_context=ctx,
                    rule_results=list(batch_results),
                )
                st.session_state[f"{key_prefix}_artifacts"] = art
                st.session_state[f"{key_prefix}_written"] = {
                    k: str(v) for k, v in written.items()
                }
            except Exception as exc:  # noqa: BLE001 — show friendly error, not Traceback page
                st.error(f"Engineering Findings report failed: {exc}")
                return

    art = st.session_state.get(f"{key_prefix}_artifacts")
    written = st.session_state.get(f"{key_prefix}_written") or {}
    if not art:
        return

    st.success(
        f"Findings ready: {art.metrics.get('n_priority_findings')} priority · "
        f"suppressed FP {art.metrics.get('n_suppressed')} · "
        f"quality gate ok={art.quality_gate.get('ok')}"
    )
    if art.quality_gate.get("errors"):
        st.warning("Quality gate errors: " + "; ".join(art.quality_gate["errors"]))
    if art.quality_gate.get("warnings"):
        st.caption("Warnings: " + "; ".join(art.quality_gate["warnings"]))

    st.markdown("##### Engineer review (optional)")
    for f in art.findings:
        cols = st.columns([3, 2, 1, 3])
        cols[0].markdown(f"**{f.finding_id}** {f.title[:60]}")
        cols[1].caption(f.effective_classification.value)
        include = cols[2].checkbox(
            "Include",
            value=f.include_in_report,
            key=f"{key_prefix}_inc_{f.finding_id}",
        )
        note = cols[3].text_input(
            "Note",
            value=(f.engineer_override or {}).get("note", ""),
            key=f"{key_prefix}_note_{f.finding_id}",
            label_visibility="collapsed",
        )
        f.include_in_report = include
        if note:
            f.engineer_override = {
                **(f.engineer_override or {}),
                "note": note,
                "automated_classification": f.classification.value,
            }

    jp = written.get("json")
    dp = written.get("docx")
    if jp and Path(jp).is_file():
        Path(jp).write_text(json.dumps(art.to_dict(), indent=2) + "\n", encoding="utf-8")
        st.download_button(
            "Download engineering_findings.json",
            data=Path(jp).read_bytes(),
            file_name=Path(jp).name,
            mime="application/json",
            key=f"{key_prefix}_dl_json",
        )
    if dp and Path(dp).is_file():
        st.download_button(
            "Download FDD Engineering Findings Report (DOCX)",
            data=Path(dp).read_bytes(),
            file_name=Path(dp).name,
            mime=MIME_DOCX,
            key=f"{key_prefix}_dl_docx",
            type="primary",
        )


def generic_rcx_bytes_for_tests() -> bytes:
    """Bytes accessor for the committed Generic RCx asset (tests / agents)."""
    return load_generic_rcx_report()
