"""Paths and equipment provenance for the residential heat-pump IDF."""
from __future__ import annotations

import os
import urllib.error
import urllib.request
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[3]
_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
DEFAULT_EPW_NAME = "USA_CO_Golden-NREL.724666_TMY3.epw"
_IDF_NAME = "residential_heat_pump_home.idf"

# Packaged assets ship inside the installed wheel (src/vibe23/assets/). Repo-root
# model/ mirrors remain for humans browsing GitHub; Studio resolves assets first.
MODEL_IDF = _ASSETS_DIR / _IDF_NAME
DEFAULT_EPW = _ASSETS_DIR / DEFAULT_EPW_NAME

# Public raw URLs used when Streamlit Cloud / a broken install is missing assets.
_GITHUB_ASSETS_BASE = (
    "https://raw.githubusercontent.com/bbartling/py-bacnet-stacks-playground/"
    "develop/vibe_code_apps_23/src/vibe23/assets"
)

DEFAULT_EPW_CANDIDATES = (
    DEFAULT_EPW,
    PACKAGE_ROOT / "model" / DEFAULT_EPW_NAME,
    PACKAGE_ROOT / "weather" / DEFAULT_EPW_NAME,
    PACKAGE_ROOT / "fixtures" / "weather" / DEFAULT_EPW_NAME,
    Path(r"C:\EnergyPlusV26-1-0\WeatherData") / DEFAULT_EPW_NAME,
    Path("/usr/local/EnergyPlus-26-1-0/WeatherData") / DEFAULT_EPW_NAME,
    Path("/opt/EnergyPlus-26-1-0/WeatherData") / DEFAULT_EPW_NAME,
    Path("/Applications/EnergyPlus-26-1-0/WeatherData") / DEFAULT_EPW_NAME,
)


def equipment_provenance() -> dict[str, str]:
    return {
        "claim_model": "HYPOTHETICAL_GL14_TUNED_DEMO_MODEL",
        "claim_assumptions": "ILLUSTRATIVE_RESIDENTIAL_ASSUMPTIONS",
        "equipment": "Carrier 50EZ060",
        "refrigerant": "R-410A",
        "nominal_tons": "5",
        "source_dataset": r"C:\EnergyPlusV26-1-0\DataSets\RooftopPackagedHeatPump.idf",
        "cooling_capacity_w": "17716.3372",
        "cooling_cop": "4.05",
        "heating_capacity_w": "17303.1085",
        "heating_cop": "4.5",
        "rated_flow_m3s": "0.944",
        "zone_timestep": "12",
        "intervals_per_day": "288",
        "internal_gains": (
            "ILLUSTRATIVE diurnal RESIDENTIAL_LIGHTS 2.0 W/m2 + RESIDENTIAL_PLUGS 2.5 W/m2 "
            "(~0.6 kW average on 325 m2; RECS-scale non-HVAC order — not ALWAYS_ON phantom)"
        ),
        "note": "Curves copied into repo IDF; install DataSets files are not modified.",
        "package_idf": f"src/vibe23/assets/{_IDF_NAME}",
        "package_epw": f"src/vibe23/assets/{DEFAULT_EPW_NAME}",
    }


def _download_asset(name: str, target: Path, *, timeout: float = 120.0) -> Path:
    """Fetch a missing demo asset from the public GitHub raw URL into target."""
    target.parent.mkdir(parents=True, exist_ok=True)
    url = f"{_GITHUB_ASSETS_BASE}/{name}"
    temporary = target.with_suffix(target.suffix + ".partial")
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = resp.read()
        if not data:
            raise OSError(f"empty download for {name}")
        temporary.write_bytes(data)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def ensure_demo_assets(*, download_if_missing: bool = True) -> dict[str, Path]:
    """Ensure packaged IDF + EPW exist for Studio / wheel installs / Streamlit Cloud.

    Resolution order for each asset:
    1. ``src/vibe23/assets/`` (wheel package data)
    2. Repo-root ``model/`` mirror
    3. Optional download from GitHub ``develop`` raw assets (Streamlit.io safety net)
    """
    resolved: dict[str, Path] = {}
    for key, name, primary, mirror in (
        ("idf", _IDF_NAME, MODEL_IDF, PACKAGE_ROOT / "model" / _IDF_NAME),
        ("epw", DEFAULT_EPW_NAME, DEFAULT_EPW, PACKAGE_ROOT / "model" / DEFAULT_EPW_NAME),
    ):
        if primary.is_file():
            resolved[key] = primary.resolve()
            continue
        if mirror.is_file():
            # Prefer copying into the package assets dir so subsequent launches are local.
            try:
                primary.parent.mkdir(parents=True, exist_ok=True)
                primary.write_bytes(mirror.read_bytes())
                resolved[key] = primary.resolve()
                continue
            except OSError:
                resolved[key] = mirror.resolve()
                continue
        if not download_if_missing:
            raise FileNotFoundError(f"demo asset missing: {name}")
        try:
            resolved[key] = _download_asset(name, primary).resolve()
        except (OSError, urllib.error.URLError, TimeoutError) as exc:
            raise FileNotFoundError(
                f"demo asset missing and download failed for {name}: {exc}"
            ) from exc
    return resolved


def find_denver_epw(explicit: Path | str | None = None) -> Path | None:
    """Locate the Golden/NREL TMY3 EPW used as the Denver-type weather file.

    Prefers the committed package copy under ``assets/`` so Studio/CLI do not
    depend on a local EnergyPlus install path.
    """

    from ..envfile import load_energyplus_env

    load_energyplus_env()
    try:
        ensure_demo_assets(download_if_missing=True)
    except FileNotFoundError:
        pass
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    # Packaged EPW before ENERGYPLUS_WEATHER so .env install paths do not win.
    candidates.append(DEFAULT_EPW)
    candidates.append(PACKAGE_ROOT / "model" / DEFAULT_EPW_NAME)
    weather = os.environ.get("ENERGYPLUS_WEATHER", "").strip()
    if weather:
        candidates.append(Path(weather).expanduser())
    weather_dir = os.environ.get("ENERGYPLUS_WEATHER_DIR", "").strip()
    root = os.environ.get("ENERGYPLUS_ROOT", "").strip()
    for folder in (weather_dir, str(Path(root) / "WeatherData") if root else ""):
        if folder:
            candidates.append(Path(folder).expanduser() / DEFAULT_EPW_NAME)
    candidates.extend(DEFAULT_EPW_CANDIDATES)
    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        # Case-preserving dedupe; only remember paths that exist so a missing
        # explicit path cannot shadow the packaged EPW on case-sensitive hosts.
        key = str(resolved)
        if key in seen:
            continue
        if resolved.is_file():
            seen.add(key)
            return resolved
        seen.add(key)
    return None
