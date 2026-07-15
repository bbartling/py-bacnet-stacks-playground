"""App 20 runtime paths and EnergyPlus Docker pin."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
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
