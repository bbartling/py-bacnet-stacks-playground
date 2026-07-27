"""Shim: rebind to open_fdd.reporting.candidates (PyPI open-fdd)."""
import open_fdd.reporting.candidates as _impl
import sys as _sys
_sys.modules[__name__] = _impl
