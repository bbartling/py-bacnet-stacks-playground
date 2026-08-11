"""Shim: rebind to open_fdd.analytics.occupancy (PyPI open-fdd)."""
import open_fdd.analytics.occupancy as _impl
import sys as _sys

_sys.modules[__name__] = _impl
