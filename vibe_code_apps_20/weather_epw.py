"""Deprecated shim — real module is :mod:`wattlab.weather.epw`."""

from wattlab.weather.epw import *  # noqa: F401,F403
from wattlab.weather.epw import main  # noqa: F401

if __name__ == "__main__":
    raise SystemExit(main())
