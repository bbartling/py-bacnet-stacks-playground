"""Deprecated shim — real module is :mod:`wattlab.calibrate` (vibe19 sidecar entrypoint)."""

from wattlab.calibrate import *  # noqa: F401,F403
from wattlab.calibrate import main  # noqa: F401

if __name__ == "__main__":
    raise SystemExit(main())
