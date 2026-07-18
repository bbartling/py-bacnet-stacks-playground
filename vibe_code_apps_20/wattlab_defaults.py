"""Deprecated shim — real module is :mod:`wattlab.defaults`."""

from wattlab.defaults import *  # noqa: F401,F403
from wattlab.defaults import main, resolve_profile  # noqa: F401

if __name__ == "__main__":
    raise SystemExit(main())
