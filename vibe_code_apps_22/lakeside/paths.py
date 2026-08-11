"""Lakeside Elementary — site data + app path resolution.

Code lives in vibe_code_apps_22. Historian / packages / E+ runs stay on the
site workspace.

Env (any one works; first wins):
  LAKESIDE_SITE_ROOT
  VIBE22_SITE_ROOT
  VIBE22_CREEKSIDE_ROOT   # legacy
  VIBE23_CREEKSIDE_ROOT   # legacy

No personal machine-path fallbacks in git. Set an env var, write ``.site_root``
(gitignored) next to this app, or place the site next to the repo parent as
``sp_creekside`` / ``sp_lakeside``.
"""
from __future__ import annotations

import os
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
SITE_ROOT_PIN = APP_ROOT / ".site_root"

BUILDING_ID = "LAKESIDE_ES"
BUILDING_LABEL = "Lakeside Elementary School"
SITE_REF = "spasd_lakeside_es"
CAMPUS_ID = "lakeside_es"
REGION_LABEL = "southern Wisconsin"


def app_root() -> Path:
    return APP_ROOT


def _valid_site(path: Path) -> bool:
    return path.is_dir() and (path / "reports").is_dir()


def remember_site_root(path: Path | str) -> Path:
    """Persist site root to ``.site_root`` and ``LAKESIDE_SITE_ROOT`` for this process."""
    p = Path(path).expanduser()
    if not _valid_site(p):
        raise FileNotFoundError(
            f"{p} is not a site workspace (expected a reports/ folder under it)."
        )
    resolved = p.resolve()
    SITE_ROOT_PIN.write_text(str(resolved) + "\n", encoding="utf-8")
    os.environ["LAKESIDE_SITE_ROOT"] = str(resolved)
    return resolved


def _pinned_site_root() -> Path | None:
    if not SITE_ROOT_PIN.is_file():
        return None
    try:
        raw = SITE_ROOT_PIN.read_text(encoding="utf-8").strip().splitlines()
    except OSError:
        return None
    if not raw:
        return None
    p = Path(raw[0].strip()).expanduser()
    return p if _valid_site(p) else None


def site_root() -> Path:
    for key in (
        "LAKESIDE_SITE_ROOT",
        "VIBE22_SITE_ROOT",
        "VIBE22_CREEKSIDE_ROOT",
        "VIBE23_CREEKSIDE_ROOT",
    ):
        val = os.environ.get(key)
        if val:
            p = Path(val)
            if not p.is_dir():
                raise FileNotFoundError(f"{key}={val} is not a directory")
            return p

    pinned = _pinned_site_root()
    if pinned is not None:
        return pinned

    candidates = [
        APP_ROOT.parent.parent / "sp_creekside",
        APP_ROOT.parent.parent / "sp_lakeside",
        APP_ROOT.parent / "sp_creekside",
        APP_ROOT.parent / "sp_lakeside",
    ]
    for c in candidates:
        if _valid_site(c):
            return c
    raise FileNotFoundError(
        "Set LAKESIDE_SITE_ROOT (or VIBE22_SITE_ROOT) to the site workspace "
        "(expected reports/ under the site root)."
    )


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
