"""Streamlit helpers for static Word / ZIP report downloads."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from app.docx_report import (
    PORTFOLIO_EXECUTIVE_DOCX,
    REPORTS_DIR,
    TEMPLATE_PACK_ZIP,
    UNIVERSAL_FINDING_DOCX,
    build_portfolio_executive_docx,
    build_rcx_family_docx,
    build_universal_finding_docx,
    load_template_pack_zip_bytes,
    rcx_family_download_label,
    rcx_family_report_filename,
    report_path,
)

MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MIME_ZIP = "application/zip"


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
        mime=MIME_ZIP if filename.lower().endswith(".zip") else MIME_DOCX,
        key=key,
        type="primary" if primary else "secondary",
        help=help or f"Serves `{filename}` from assets/reports.",
        use_container_width=use_container_width,
    )
    return True


def render_rcx_family_downloads(family: str, *, key_prefix: str = "rcx") -> None:
    """Primary family template + secondary universal finding sheet for a mechanical tab."""
    fname = rcx_family_report_filename(family)
    report_download_button(
        filename=fname,
        label=rcx_family_download_label(family),
        key=f"{key_prefix}_primary_{fname}",
        primary=True,
        help=f"Primary template for **{family}** (`{fname}`).",
    )
    c1, c2 = st.columns(2)
    with c1:
        report_download_button(
            filename=UNIVERSAL_FINDING_DOCX,
            label="Universal Finding Sheet",
            key=f"{key_prefix}_universal_{family}",
            help="One-fault documentation sheet — secondary download.",
        )
    with c2:
        # Portfolio is more of a central/pack item; still handy beside family work.
        report_download_button(
            filename=PORTFOLIO_EXECUTIVE_DOCX,
            label="Portfolio Executive Report",
            key=f"{key_prefix}_portfolio_{family}",
            help="Multi-system / multi-building executive narrative.",
        )


def render_central_template_pack_section(*, key_prefix: str = "export") -> None:
    """Export / Help hierarchy: ZIP pack primary, then secondary sheets, then individuals."""
    st.markdown("##### RCx / report Word templates")
    st.caption(
        f"Static files under `{REPORTS_DIR.name}/`. "
        "Mechanical-tab downloads are primary for day-to-day work; "
        "use the complete ZIP when you want every template at once."
    )

    report_download_button(
        filename=TEMPLATE_PACK_ZIP,
        label="Download Complete RCx Template Pack (ZIP)",
        key=f"{key_prefix}_template_pack_zip",
        primary=True,
        help="All family templates + portfolio, universal finding, catalog, analytics, data-model.",
    )

    c1, c2 = st.columns(2)
    with c1:
        report_download_button(
            filename=UNIVERSAL_FINDING_DOCX,
            label="Universal Finding Sheet",
            key=f"{key_prefix}_universal",
        )
    with c2:
        report_download_button(
            filename=PORTFOLIO_EXECUTIVE_DOCX,
            label="Portfolio Executive Report",
            key=f"{key_prefix}_portfolio",
        )

    with st.expander("Individual templates (all mechanical families)", expanded=False):
        from app.docx_report import rcx_families

        for fam in rcx_families():
            fname = rcx_family_report_filename(fam)
            report_download_button(
                filename=fname,
                label=rcx_family_download_label(fam),
                key=f"{key_prefix}_indiv_{fname}",
                use_container_width=True,
            )
        report_download_button(
            filename="rcx_catalog.docx",
            label="Download RCx catalog DOCX",
            key=f"{key_prefix}_catalog",
        )
        report_download_button(
            filename="data_model.docx",
            label="Download data_model.docx",
            key=f"{key_prefix}_data_model",
        )
        report_download_button(
            filename="analytics.docx",
            label="Download analytics.docx",
            key=f"{key_prefix}_analytics",
        )


# Keep import-side smoke helpers used by tests without Streamlit.
def template_pack_bytes_for_tests() -> bytes:
    return load_template_pack_zip_bytes()


def family_docx_bytes_for_tests(family: str) -> bytes:
    return build_rcx_family_docx(family)


def universal_docx_bytes_for_tests() -> bytes:
    return build_universal_finding_docx()


def portfolio_docx_bytes_for_tests() -> bytes:
    return build_portfolio_executive_docx()
