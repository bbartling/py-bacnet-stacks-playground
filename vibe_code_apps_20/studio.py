"""WattLab Studio — dump + energy upload → ESCO dashboard → twin → ECMs.

Launch: ``wattlab studio`` or ``streamlit run studio.py``.
AI agents (Codex) work on the shared workspace folder outside Streamlit.
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


def main() -> None:
    ensure_workspace()
    invalidate_dependent_state(
        st.session_state,
        profile=st.session_state.get("studio_profile"),
        bundle=st.session_state.get("studio_bundle"),
    )
    st.sidebar.title("WattLab Studio")
    st.sidebar.caption(
        "Uploads → Fuel dashboard → Twin / calibrate → ECMs. "
        "Chat with Codex on the workspace folder; this UI is the viewer."
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
