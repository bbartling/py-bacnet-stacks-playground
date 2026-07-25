"""WattLab Studio — dump + energy upload → ESCO dashboard → twin → ECMs.

Launch: ``wattlab studio`` or ``streamlit run studio.py``.
AI agents work on the shared workspace folder outside Streamlit; Studio is the browser viewer.
"""

from __future__ import annotations

import os

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


def _docker_image_caption() -> str | None:
    """Human-readable GHCR/local image identity (matches vibe19 sidebar style)."""
    ref = (os.environ.get("VIBE20_IMAGE_REF") or "").strip()
    tag = (os.environ.get("VIBE20_IMAGE_TAG") or "").strip()
    sha = (os.environ.get("VIBE20_GIT_SHA") or "").strip()
    if not ref and not tag and not sha:
        return None
    name = f"{ref}:{tag}" if ref and tag else (ref or tag or "vibe20")
    short = sha[:12] if sha and sha != "unknown" else ""
    return f"Image: `{name}`" + (f" · sha `{short}`" if short else "")


def _show_bootstrap_result(result: dict) -> None:
    """Surface only actionable bootstrap issues (no long green success banners)."""
    for note in result.get("needs_input") or []:
        st.sidebar.info(f"NEEDS_INPUT: {note}")
    for warn in result.get("warnings") or []:
        st.sidebar.caption(str(warn))
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
    if result.get("errors") or result.get("needs_input") or result.get("warnings"):
        _show_bootstrap_result(result)


def _render_bootstrap_sidebar_controls() -> None:
    """Short Re-apply control; warn only when bootstrap file changed on disk."""
    from wattlab.studio.bootstrap import (
        apply_bootstrap_to_session,
        bootstrap_file_mtime,
        clear_bootstrap_session_flags,
        resolve_bootstrap_path,
    )

    path = resolve_bootstrap_path()
    if path is None:
        return

    applied_mtime = st.session_state.get("_studio_bootstrap_applied_mtime")
    current_mtime = bootstrap_file_mtime(path)
    if (
        st.session_state.get("_studio_bootstrapped")
        and applied_mtime is not None
        and current_mtime is not None
        and current_mtime > float(applied_mtime) + 0.01
    ):
        st.sidebar.warning("Bootstrap file updated on disk.")

    if st.sidebar.button(
        "Re-apply bootstrap",
        key="studio_reapply_bootstrap",
        help="Reload Fuel/Twin/ECM session state from studio_bootstrap.json",
    ):
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
        if result.get("applied") and not (result.get("errors") or result.get("needs_input")):
            st.sidebar.caption("Bootstrap re-applied.")
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
    img_cap = _docker_image_caption()
    if img_cap:
        st.sidebar.caption(img_cap)
    st.sidebar.caption("Uploads → Fuel → Twin → ECMs")
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
