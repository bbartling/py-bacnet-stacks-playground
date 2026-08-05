"""Lakeside Elementary — site data + app path resolution.

Code lives in vibe_code_apps_22. Historian / packages / E+ runs stay on the
site workspace (default: Desktop/testing/sp_creekside until folder renamed).

Env (any one works; first wins):
  LAKESIDE_SITE_ROOT
  VIBE22_SITE_ROOT
  VIBE22_CREEKSIDE_ROOT   # legacy
  VIBE23_CREEKSIDE_ROOT   # legacy
"""
from __future__ import annotations

import os
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]

BUILDING_ID = "LAKESIDE_ES"
BUILDING_LABEL = "Lakeside Elementary School"
SITE_REF = "spasd_lakeside_es"
CAMPUS_ID = "lakeside_es"
REGION_LABEL = "southern Wisconsin"

_DEFAULT_SITE = Path(r"C:\Users\ben\OneDrive\Desktop\testing\sp_creekside")


def app_root() -> Path:
    return APP_ROOT


def site_root() -> Path:
    for key in (
        "LAKESIDE_SITE_ROOT",
        "VIBE22_SITE_ROOT",
        "VIBE22_CREEKSIDE_ROOT",
        "VIBE23_CREEKSIDE_ROOT",
    ):
        val = os.environ.get(key)
        if val:
            return Path(val)

    candidates = [
        APP_ROOT.parent.parent / "sp_creekside",
        APP_ROOT.parent.parent / "sp_lakeside",
        Path.home() / "OneDrive" / "Desktop" / "testing" / "sp_creekside",
        Path.home() / "OneDrive" / "Desktop" / "testing" / "sp_lakeside",
        _DEFAULT_SITE,
    ]
    for c in candidates:
        if c.is_dir() and (c / "reports").is_dir():
            return c
    return _DEFAULT_SITE


def clean_data_building_dir() -> Path:
    """Prefer LAKESIDE_ES; fall back to legacy CREEKSIDE_ES if not yet renamed."""
    root = site_root() / "clean_data"
    preferred = root / BUILDING_ID
    if preferred.is_dir():
        return preferred
    legacy = root / "CREEKSIDE_ES"
    if legacy.is_dir():
        return legacy
    return preferred


def weather_history_csv() -> Path:
    return clean_data_building_dir() / "weather" / "history_wide.csv"


def demand_hourly_csv() -> Path:
    return site_root() / "reports" / "demand_vs_web_weather_hourly.csv"


def eplus_dir() -> Path:
    return site_root() / "eplus"


def reports_dir() -> Path:
    return site_root() / "reports"


def packages_dir() -> Path:
    return site_root() / "packages"


def utilities_dir() -> Path:
    return site_root() / "utilities"


def pinned_eplus_models_dir() -> Path:
    """Repo-pinned IdealLoads champions (git). Prefer site copy when present."""
    return APP_ROOT / "models" / "eplus"


def resolve_eplus_model(name: str) -> Path:
    """Resolve an IDF: site eplus/models first, then repo models/eplus/."""
    site = eplus_dir() / "models" / name
    if site.is_file():
        return site
    pinned = pinned_eplus_models_dir() / name
    if pinned.is_file():
        return pinned
    return site

