"""Shim: rebind to open_fdd.reporting.models (PyPI open-fdd)."""
import open_fdd.reporting.models as _impl
import sys as _sys
_sys.modules[__name__] = _impl
