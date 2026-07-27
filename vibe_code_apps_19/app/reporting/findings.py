"""Shim: rebind to open_fdd.reporting.findings (PyPI open-fdd)."""
import open_fdd.reporting.findings as _impl
import sys as _sys
_sys.modules[__name__] = _impl
