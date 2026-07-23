"""App 20 runtime paths and EnergyPlus Docker pin."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def _detect_root() -> Path:
    """Repo root (``vibe_code_apps_20``), even when wattlab is installed as a wheel.

    Editable installs keep ``examples/`` next to the package parent. The GHCR
    image ``pip install .`` puts code in site-packages while ``examples/`` stays
    under ``/app`` — prefer ``WATTLAB_ROOT``, then a tree that contains prototypes.
    """
    env = (os.environ.get("WATTLAB_ROOT") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    pkg_parent = Path(__file__).resolve().parents[1]
    if (pkg_parent / "examples" / "prototypes").is_dir():
        return pkg_parent
    for cand in (Path.cwd(), Path("/app"), pkg_parent.parent):
        try:
            resolved = cand.resolve()
        except OSError:
            continue
        if (resolved / "examples" / "prototypes").is_dir():
            return resolved
    return pkg_parent


def artifacts_root() -> Path:
    """Writable run/artifact directory.

    Prefer ``WATTLAB_ARTIFACTS``, else ``WATTLAB_STUDIO_WORKSPACE/.artifacts``
    (bind-mounted host path — required for Docker-from-Studio / DinD), else
    ``<ROOT>/.artifacts``.
    """
    env = (os.environ.get("WATTLAB_ARTIFACTS") or "").strip()
    if env:
        p = Path(env).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p
    ws = (os.environ.get("WATTLAB_STUDIO_WORKSPACE") or "").strip()
    if ws:
        p = Path(ws).expanduser().resolve() / ".artifacts"
        p.mkdir(parents=True, exist_ok=True)
        return p
    p = ROOT / ".artifacts"
    p.mkdir(parents=True, exist_ok=True)
    return p


def host_path_for_docker(path: Path | str) -> Path:
    """Map container paths to host paths when the Docker daemon is the host.

    With ``-v HOST:CONTAINER`` and docker.sock, ``docker run -v`` sources must be
    **host** paths. Set ``WATTLAB_HOST_WORKSPACE`` to the host side of
    ``WATTLAB_STUDIO_WORKSPACE`` (e.g. ``/home/ben/wattlab_workspace`` ↔ ``/data``).
    """
    p = Path(path).resolve()
    host_ws = (os.environ.get("WATTLAB_HOST_WORKSPACE") or "").strip()
    cont_ws = (os.environ.get("WATTLAB_STUDIO_WORKSPACE") or "").strip()
    if not host_ws or not cont_ws:
        return p
    cont = Path(cont_ws).expanduser().resolve()
    try:
        rel = p.relative_to(cont)
    except ValueError:
        return p
    return (Path(host_ws).expanduser().resolve() / rel)


ROOT = _detect_root()
# Backward-compat name: many modules import ARTIFACTS. Re-bind after env is set
# at process start (Studio sets WATTLAB_STUDIO_WORKSPACE before importing wattlab).
ARTIFACTS = artifacts_root()
EXAMPLES = ROOT / "examples"
PROTOTYPES = EXAMPLES / "prototypes"
WEATHER = EXAMPLES / "weather"
THIRD_PARTY = ROOT / "third_party"
ENERGYPLUS_MCP = THIRD_PARTY / "EnergyPlus-MCP"

DOCKER_IMAGE = (os.environ.get("ENERGYPLUS_MCP_IMAGE") or "energyplus-mcp-dev").strip()


def resolve_energyplus_mcp_path() -> Path:
    """Locate LBNL EnergyPlus-MCP vendor tree (workspace-first for tip agents).

    Order: ``WATTLAB_ENERGYPLUS_MCP`` → ``$WATTLAB_STUDIO_WORKSPACE/third_party/EnergyPlus-MCP``
    (if present) → legacy ``ROOT/third_party/EnergyPlus-MCP`` → workspace target if set.
    """
    env = (os.environ.get("WATTLAB_ENERGYPLUS_MCP") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    ws = (os.environ.get("WATTLAB_STUDIO_WORKSPACE") or "").strip()
    ws_cand = (
        Path(ws).expanduser().resolve() / "third_party" / "EnergyPlus-MCP" if ws else None
    )
    if ws_cand is not None and (ws_cand / "energyplus-mcp-server").is_dir():
        return ws_cand
    legacy = ENERGYPLUS_MCP.resolve()
    if (legacy / "energyplus-mcp-server").is_dir():
        return legacy
    if ws_cand is not None:
        return ws_cand
    return legacy
EP_VERSION_PIN = "26.1.0"
DEFAULT_PROTOTYPE_IDF = PROTOTYPES / "5ZoneAirCooled.idf"
# Closest bundled TMY3 for Madison WI conceptual screening (no WI EPW in vendor samples).
DEFAULT_MADISON_EPW = WEATHER / "USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw"
DEFAULT_EPW_NOTE = (
    "Madison climate approximated with Chicago O'Hare TMY3 from EnergyPlus-MCP "
    "illustrative examples; replace with a true Madison WI EPW when available."
)

# Default electricity rate for conceptual cost fields (USD/kWh) when profile omits utility.
DEFAULT_ELEC_RATE_USD_PER_KWH = float(os.environ.get("VIBE20_ELEC_RATE") or "0.12")
DEFAULT_GAS_RATE_USD_PER_THERM = float(os.environ.get("VIBE20_GAS_RATE") or "0.80")

# Weather suitability modes — stamp on every result / scorecard (never silent substitute).
TYPICAL_YEAR_SCREENING = "TYPICAL_YEAR_SCREENING"
ACTUAL_YEAR_CALIBRATION = "ACTUAL_YEAR_CALIBRATION"
SUBSTITUTE_CLIMATE_CONCEPTUAL_ONLY = "SUBSTITUTE_CLIMATE_CONCEPTUAL_ONLY"

# Calibration status enum (scorecard ``status``; ``overall`` kept for backward compat).
STATUS_VALIDATED = "VALIDATED"
STATUS_CALIBRATED_NOT_VALIDATED = "CALIBRATED_NOT_VALIDATED"
STATUS_FAILED_VALIDATION = "FAILED_VALIDATION"
STATUS_CONCEPTUAL_ONLY = "CONCEPTUAL_ONLY"

# 5ZoneAirCooled prototype footprint (~927 m2) — for honesty banners / scale.
PROTOTYPE_AREA_FT2_NOMINAL = 9977.0


def weather_suitability(
    *,
    source: str | None = None,
    epw_path: Path | str | None = None,
    epw_note: str | None = None,
    city_id: str | None = None,
) -> dict[str, Any]:
    """Classify weather file honesty for reports.

    Modes:
      TYPICAL_YEAR_SCREENING — city-matched TMY / typical year (screening OK).
      ACTUAL_YEAR_CALIBRATION — AMY EPW from measured/observed weather.
      SUBSTITUTE_CLIMATE_CONCEPTUAL_ONLY — wrong-city or approximate EPW.
    """
    src = (source or "").strip().lower()
    note = (epw_note or "").strip()
    note_l = note.lower()
    city = (city_id or "").strip().lower()
    epw = Path(epw_path) if epw_path else None
    epw_name = epw.name.lower() if epw else ""

    substitute_hints = (
        "approximat",
        "substitut",
        "closest bundled",
        "until",
        "screening only",
        "replace with",
        "conceptual only",
        "no catalog epw",
    )
    is_chicago_epw = "chicago" in epw_name or "ohare" in epw_name or "725300" in epw_name
    city_is_chicago = city in {"chicago", "chi", ""}

    if any(h in note_l for h in substitute_hints):
        return {
            "mode": SUBSTITUTE_CLIMATE_CONCEPTUAL_ONLY,
            "reason": note or DEFAULT_EPW_NOTE,
        }
    if is_chicago_epw and city and not city_is_chicago:
        return {
            "mode": SUBSTITUTE_CLIMATE_CONCEPTUAL_ONLY,
            "reason": note
            or (
                f"Chicago O'Hare TMY3 used for city={city!r}; "
                "not valid for measured-year calibration."
            ),
        }
    if epw is not None and DEFAULT_MADISON_EPW.is_file() and epw.resolve() == DEFAULT_MADISON_EPW.resolve() and city and not city_is_chicago:
        return {
            "mode": SUBSTITUTE_CLIMATE_CONCEPTUAL_ONLY,
            "reason": note or DEFAULT_EPW_NOTE,
        }

    if src in {"amy", "actual", "actual_year", ACTUAL_YEAR_CALIBRATION.lower()}:
        return {
            "mode": ACTUAL_YEAR_CALIBRATION,
            "reason": note
            or "Actual Meteorological Year EPW built from observed weather for the measured period.",
        }

    return {
        "mode": TYPICAL_YEAR_SCREENING,
        "reason": note
        or "Typical-year EPW matched to project city (standardized annual screening).",
    }


def load_dotenv(path: Path | None = None) -> Path | None:
    """Minimal .env loader (no python-dotenv dependency)."""
    p = path or (ROOT / ".env")
    if not p.is_file():
        return None
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val
    return p
