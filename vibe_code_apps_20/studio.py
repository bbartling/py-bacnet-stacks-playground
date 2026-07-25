"""WattLab Studio — dump + energy upload → ESCO dashboard → twin → ECMs.

Launch: ``wattlab studio`` or ``streamlit run studio.py``.
AI agents work on the shared workspace folder outside Streamlit; Studio is the browser viewer.
"""

from __future__ import annotations

import streamlit as st

from wattlab.studio.proxies import estimate_proxy_savings  # noqa: F401  (re-export for tests)
from wattlab.studio.state import invalidate_dependent_state
from wattlab.studio.workspace import ensure_workspace

st.set_page_config(page_title="OpenFDD Vibe 20", page_icon="⚡", layout="wide")

PAGES = [
    "Uploads",
    "Fuel dashboard",
    "Twin / calibrate",
    "ECMs",
]


def _show_bootstrap_result(result: dict) -> None:
    if result.get("banner"):
        st.sidebar.success(result["banner"])
    for note in result.get("needs_input") or []:
        st.sidebar.info(f"NEEDS_INPUT: {note}")
    for warn in result.get("warnings") or []:
        st.sidebar.caption(f"Bootstrap: {warn}")
    for err in result.get("errors") or []:
        st.sidebar.warning(err)


def _apply_studio_bootstrap_once() -> None:
    """Auto-load Fuel/Twin from studio_bootstrap.json (once per browser session)."""
    # Avoid SessionState.__getattr__("get") — use `in` / [].
    if "_studio_bootstrapped" in st.session_state and st.session_state["_studio_bootstrapped"]:
        return
    try:
        from wattlab.studio.bootstrap import apply_bootstrap_to_session

        result = apply_bootstrap_to_session(st.session_state)
    except Exception as exc:  # noqa: BLE001 — never crash Studio on bootstrap
        st.session_state["_studio_bootstrapped"] = True
        st.sidebar.warning(f"Bootstrap skipped: {exc}")
        return
    if result.get("skipped") == "no_bootstrap_file":
        return
    if result.get("applied") or result.get("errors") or result.get("needs_input"):
        _show_bootstrap_result(result)


def _render_bootstrap_sidebar_controls() -> None:
    """Discoverability: path caption, stale-file warning, Re-apply button."""
    from wattlab.studio.bootstrap import (
        apply_bootstrap_to_session,
        bootstrap_file_mtime,
        clear_bootstrap_session_flags,
        resolve_bootstrap_path,
    )

    path = resolve_bootstrap_path()
    if path is None:
        return

    st.sidebar.caption(
        f"Bootstrap: `{path.name}` — page refresh starts a new session; "
        "or use Re-apply below."
    )
    applied_mtime = st.session_state.get("_studio_bootstrap_applied_mtime")
    current_mtime = bootstrap_file_mtime(path)
    if (
        st.session_state.get("_studio_bootstrapped")
        and applied_mtime is not None
        and current_mtime is not None
        and current_mtime > float(applied_mtime) + 0.01
    ):
        st.sidebar.warning("Bootstrap file updated — Re-apply or refresh.")

    if st.sidebar.button("Re-apply bootstrap", key="studio_reapply_bootstrap"):
        clear_bootstrap_session_flags(st.session_state)
        try:
            result = apply_bootstrap_to_session(st.session_state)
        except Exception as exc:  # noqa: BLE001
            st.session_state["_studio_bootstrapped"] = True
            st.sidebar.warning(f"Re-apply failed: {exc}")
            return
        if result.get("skipped") == "no_bootstrap_file":
            st.sidebar.info("No bootstrap file found.")
            return
        _show_bootstrap_result(result)


def main() -> None:
    ensure_workspace()
    _apply_studio_bootstrap_once()
    invalidate_dependent_state(
        st.session_state,
        profile=st.session_state.get("studio_profile"),
        bundle=st.session_state.get("studio_bundle"),
    )
    st.sidebar.title("OpenFDD Vibe 20")
    st.sidebar.caption(
        "WattLab Studio · Uploads → Fuel → Twin → ECMs. "
        "AI agents work on the workspace folder; this UI is the viewer."
    )
    _render_bootstrap_sidebar_controls()
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
