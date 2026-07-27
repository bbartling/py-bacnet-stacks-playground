"""Shim: rebind to open_fdd.reporting.pipeline (PyPI open-fdd)."""
import open_fdd.reporting.pipeline as _impl
import sys as _sys
_sys.modules[__name__] = _impl
