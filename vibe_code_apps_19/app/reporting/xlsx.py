"""Shim: rebind to open_fdd.reporting.xlsx (PyPI open-fdd)."""
import open_fdd.reporting.xlsx as _impl
import sys as _sys
_sys.modules[__name__] = _impl
