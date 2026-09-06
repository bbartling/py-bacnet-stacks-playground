"""Paths and equipment provenance for the residential heat-pump IDF."""
from __future__ import annotations

import os
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[3]
MODEL_IDF = PACKAGE_ROOT / "model" / "residential_heat_pump_home.idf"
DEFAULT_EPW_NAME = "USA_CO_Golden-NREL.724666_TMY3.epw"
# Packaged Golden/NREL EPW lives next to the demo IDF (committed). Local EnergyPlus
# install paths remain as optional fallbacks for CLI/dev only — Studio uses Render.
DEFAULT_EPW = PACKAGE_ROOT / "model" / DEFAULT_EPW_NAME
DEFAULT_EPW_CANDIDATES = (
    DEFAULT_EPW,
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
        "package_idf": f"model/{MODEL_IDF.name}",
        "package_epw": f"model/{DEFAULT_EPW_NAME}",
    }


def find_denver_epw(explicit: Path | str | None = None) -> Path | None:
    """Locate the Golden/NREL TMY3 EPW used as the Denver-type weather file.

    Prefers the committed package copy under ``model/`` so Studio/CLI do not
    depend on a local EnergyPlus install path.
    """

    from ..envfile import load_energyplus_env

    load_energyplus_env()
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    # Packaged EPW before ENERGYPLUS_WEATHER so .env install paths do not win.
    candidates.append(DEFAULT_EPW)
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
