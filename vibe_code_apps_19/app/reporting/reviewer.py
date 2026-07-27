"""Shim: rebind to open_fdd.reporting.reviewer (PyPI open-fdd)."""
import open_fdd.reporting.reviewer as _impl
import sys as _sys
_sys.modules[__name__] = _impl
