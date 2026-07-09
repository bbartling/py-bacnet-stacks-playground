"""Smoke test — Streamlit app imports."""

from __future__ import annotations

import pytest


@pytest.mark.skipif(
    __import__("importlib").util.find_spec("streamlit") is None,
    reason="streamlit not installed",
)
def test_streamlit_app_imports():
    import streamlit_app  # noqa: F401

    assert True
