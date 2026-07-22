"""WattLab Studio — dump + energy upload → ESCO dashboard → twin → ECMs.

Launch: ``wattlab studio`` or ``streamlit run studio.py``.
AI agents work on the shared workspace folder outside Streamlit; Studio is the browser viewer.
"""

from __future__ import annotations

import streamlit as st

from wattlab.studio.proxies import estimate_proxy_savings  # noqa: F401  (re-export for tests)
from wattlab.studio.state import invalidate_dependent_state
from wattlab.studio.workspace import ensure_workspace

st.set_page_config(page_title="WattLab Studio", page_icon="⚡", layout="wide")

PAGES = [
    "Uploads",
    "Fuel dashboard",
    "Twin / calibrate",
    "ECMs",
]


def _apply_studio_bootstrap_once() -> None:
    """Auto-load Fuel/Twin from studio_bootstrap.json (once per browser session)."""
    if st.session_state.get("_studio_bootstrapped"):
        return
    try:
        from wattlab.studio.bootstrap import apply_bootstrap_to_session

        result = apply_bootstrap_to_session(st.session_state)
    except Exception as exc:  # noqa: BLE001 — never crash Studio on bootstrap
        st.session_state["_studio_bootstrapped"] = True
        st.sidebar.warning(f"Bootstrap skipped: {exc}")
        return
    if result.get("banner"):
        st.sidebar.success(result["banner"])
    for note in result.get("needs_input") or []:
        st.sidebar.info(f"NEEDS_INPUT: {note}")


def main() -> None:
    ensure_workspace()
    _apply_studio_bootstrap_once()
    invalidate_dependent_state(
        st.session_state,
        profile=st.session_state.get("studio_profile"),
        bundle=st.session_state.get("studio_bundle"),
    )
    st.sidebar.title("WattLab Studio")
    st.sidebar.caption(
        "Uploads → Fuel dashboard → Twin / calibrate → ECMs. "
        "AI agents work on the workspace folder; this UI is the viewer."
    )
    page = st.sidebar.radio("Workflow", PAGES, key="studio_page")

    if page == "Uploads":
        from wattlab.studio.pages.uploads import render

        render()
    elif page == "Fuel dashboard":
        from wattlab.studio.pages.fuel_dashboard import render

        render(campus=st.session_state.get("studio_campus"))
    elif page == "Twin / calibrate":
        from wattlab.studio.pages.twin_calibrate import render

        render()
    else:
        from wattlab.studio.pages.ecms import render

        render()


main()
