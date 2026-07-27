"""Shim: rebind to open_fdd.reporting.day_zoom (PyPI open-fdd)."""
import open_fdd.reporting.day_zoom as _impl
import sys as _sys
_sys.modules[__name__] = _impl
