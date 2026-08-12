"""Site workspace path resolution (any building).

Code lives in vibe_code_apps_22. Historian / packages / E+ runs stay on the
site workspace. Lakeside / Creekside / ``sp_creekside`` are **practice packs**,
not code defaults.

Resolution order:
  1. Env: SITE_ROOT / LAKESIDE_SITE_ROOT / VIBE22_* (CI / one-off)
  2. Local ``config.py`` ``SITE_ROOT`` (prototype — copy from config.example.py)
  3. Gitignored ``.site_root`` pin
  4. Sibling practice-pack folder heuristics

No personal machine-path fallbacks in git. Prefer editing ``config.py``.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
SITE_ROOT_PIN = APP_ROOT / ".site_root"
_LOCAL_CONFIG = APP_ROOT / "config.py"

# Practice-pack identity only (example data under Desktop sp_creekside).
# Live product code must not require these.
BUILDING_ID = "LAKESIDE_ES"
BUILDING_LABEL = "Lakeside Elementary School"
SITE_REF = "spasd_lakeside_es"
CAMPUS_ID = "lakeside_es"
REGION_LABEL = "southern Wisconsin"


def app_root() -> Path:
    return APP_ROOT


def archived_ml_dir() -> Path:
    """Parked GL14 / farm helpers. Not a live ML product."""
    return APP_ROOT / "archive" / "ml"


def ensure_eplus_helpers_on_path() -> Path:
    helper = archived_ml_dir()
    if helper.is_dir() and str(helper) not in sys.path:
        sys.path.insert(0, str(helper))
    return helper


ensure_eplus_helpers_on_path()


def _valid_site(path: Path) -> bool:
    return path.is_dir() and (path / "reports").is_dir()


def remember_site_root(path: Path | str) -> Path:
    """Persist site root to ``.site_root`` and env for this process."""
    p = Path(path).expanduser()
    if not _valid_site(p):
        raise FileNotFoundError(
            f"{p} is not a site workspace (expected a reports/ folder under it)."
        )
    resolved = p.resolve()
    SITE_ROOT_PIN.write_text(str(resolved) + "\n", encoding="utf-8")
    os.environ["SITE_ROOT"] = str(resolved)
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


def _config_site_root() -> Path | None:
    """Load SITE_ROOT from local config.py next to the app (prototype)."""
    if not _LOCAL_CONFIG.is_file():
        return None
    try:
        spec = importlib.util.spec_from_file_location("vibe22_local_config", _LOCAL_CONFIG)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception:  # noqa: BLE001
        return None
    raw = getattr(mod, "SITE_ROOT", None)
    if raw is None or raw == "":
        return None
    p = Path(raw).expanduser()
    return p if _valid_site(p) else None


def site_root() -> Path:
    for key in (
        "SITE_ROOT",
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

    cfg = _config_site_root()
    if cfg is not None:
        return cfg

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
        "Set SITE_ROOT in config.py (copy config.example.py), or set env "
        "SITE_ROOT / LAKESIDE_SITE_ROOT to a site workspace (expected reports/)."
    )


def site_slug(site: Path | None = None) -> str:
    """Filesystem-safe slug for AMY EPW names (from campus_id or folder)."""
    root = Path(site) if site is not None else site_root()
    campus = root / "utilities" / "campus_utility.json"
    if not campus.is_file():
        campus = root / "utilities" / "campus.json"
    if campus.is_file():
        try:
            import json

            doc = json.loads(campus.read_text(encoding="utf-8"))
            cid = str(doc.get("campus_id") or "").strip()
            if cid:
                return "".join(c if c.isalnum() or c in "-_" else "_" for c in cid).strip(
                    "_-"
                ).lower() or root.name.lower()
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    return root.name.lower().replace(" ", "_")


def clean_data_building_dir() -> Path:
    """Prefer practice LAKESIDE_ES; fall back to legacy CREEKSIDE_ES."""
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
