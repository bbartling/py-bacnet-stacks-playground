"""Shim: rebind to open_fdd.analytics.rcx_plots (PyPI open-fdd). Streamlit UI stays local."""
import open_fdd.analytics.rcx_plots as _impl
import sys as _sys

_sys.modules[__name__] = _impl
