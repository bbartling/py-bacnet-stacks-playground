"""Streamlit helpers for Engineering Findings Report downloads."""

from __future__ import annotations

import json
from pathlib import Path

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


def render_engineering_findings_panel(
    *,
    batch_results: list | None = None,
    building_name: str = "",
    analysis_period: str = "",
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
        st.info("Run Rules first so FAULT rows are available for evidence review.")
        return

    if st.button(
        "Generate FDD Engineering Findings Report",
        key=f"{key_prefix}_generate",
        type="primary",
    ):
        with st.spinner("Evidence review + charts…"):
            from app.reporting.pipeline import build_engineering_findings, render_engineering_report

            art = build_engineering_findings(
                building=building_name or "Building",
                analysis_period=analysis_period,
                rule_results=list(batch_results),
            )
            buf_dir = Path(st.session_state.get("_eng_findings_tmpdir") or "/tmp/vibe19_eng_findings")
            buf_dir.mkdir(parents=True, exist_ok=True)
            st.session_state["_eng_findings_tmpdir"] = str(buf_dir)
            written = render_engineering_report(
                art, buf_dir, docx=True, json_out=True, charts=True
            )
            st.session_state[f"{key_prefix}_artifacts"] = art
            st.session_state[f"{key_prefix}_written"] = {k: str(v) for k, v in written.items()}

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
