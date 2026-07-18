"""App 20 runtime paths and EnergyPlus Docker pin."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# Repo root (vibe_code_apps_20) — one level above the wattlab package.
ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / ".artifacts"
EXAMPLES = ROOT / "examples"
PROTOTYPES = EXAMPLES / "prototypes"
WEATHER = EXAMPLES / "weather"
THIRD_PARTY = ROOT / "third_party"
ENERGYPLUS_MCP = THIRD_PARTY / "EnergyPlus-MCP"

DOCKER_IMAGE = (os.environ.get("ENERGYPLUS_MCP_IMAGE") or "energyplus-mcp-dev").strip()
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
    if epw is not None and epw.resolve() == DEFAULT_MADISON_EPW.resolve() and city and not city_is_chicago:
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
