"""Deprecated shim — real module is :mod:`wattlab.bridge`."""

from wattlab.bridge import *  # noqa: F401,F403
from wattlab.bridge import main  # noqa: F401

if __name__ == "__main__":
    raise SystemExit(main())
