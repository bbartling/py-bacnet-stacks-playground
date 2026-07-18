"""Deprecated shim — real module is :mod:`wattlab.easy_button` (vibe19 sidecar entrypoint)."""

from wattlab.easy_button import *  # noqa: F401,F403
from wattlab.easy_button import main  # noqa: F401

if __name__ == "__main__":
    raise SystemExit(main())
