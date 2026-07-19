"""Parse EnergyPlus ``eplusout.csv`` into tidy outdoor / zone / HVAC frames.

Inspired by EnergyPlusAPIHelper demo viz patterns (OA vs zone, multi-zone
temps) but post-sim only — no host-side ``pyenergyplus`` Runtime API.
Column discovery is substring-based so zone names stay dynamic.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

# Max rows returned for UI charting (downsample by stride if longer).
DEFAULT_UI_MAX_POINTS = 2000


@dataclass
class EplusTimeseries:
    """Tidy slices of an EnergyPlus CSV variable output."""

    path: Path
    outdoor: pd.DataFrame = field(default_factory=pd.DataFrame)
    zones: pd.DataFrame = field(default_factory=pd.DataFrame)
    hvac: pd.DataFrame = field(default_factory=pd.DataFrame)
    facility: pd.DataFrame = field(default_factory=pd.DataFrame)
    columns_discovered: dict[str, list[str]] = field(default_factory=dict)

    def zone_mean_temps(self) -> pd.DataFrame:
        """One row per zone: mean / min / max air temperature (°C if SI)."""
        if self.zones.empty or "zone" not in self.zones.columns:
            return pd.DataFrame(columns=["zone", "mean_c", "min_c", "max_c", "n"])
        g = self.zones.groupby("zone", sort=True)["temp_c"]
        out = g.agg(mean_c="mean", min_c="min", max_c="max", n="count").reset_index()
        return out


def _norm_header(h: str) -> str:
    return re.sub(r"\s+", " ", (h or "").strip().lower())


def _find_col(headers: list[str], *needles: str) -> int | None:
    for i, h in enumerate(headers):
        if all(n in h for n in needles):
            return i
    return None


def _find_all(headers: list[str], *needles: str) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for i, h in enumerate(headers):
        if all(n in h for n in needles):
            out.append((i, h))
    return out


def _zone_name_from_header(header: str) -> str:
    """Extract zone name from e.g. 'ZONE1:Zone Mean Air Temperature [C](Hourly)'."""
    raw = header.strip()
    # Drop trailing unit / frequency annotations
    base = re.split(r"\s*\[", raw, maxsplit=1)[0]
    if ":" in base:
        return base.split(":", 1)[0].strip()
    return base.strip() or "zone"


def _parse_float(token: str) -> float:
    try:
        return float(token)
    except (TypeError, ValueError):
        return float("nan")


def find_eplusout_csv(sim_dir: Path | str) -> Path | None:
    root = Path(sim_dir)
    direct = root / "eplusout.csv"
    if direct.is_file():
        return direct
    alts = sorted(root.glob("eplusout*.csv"))
    return alts[0] if alts else None


def parse_eplusout_timeseries(path: Path | str) -> EplusTimeseries:
    """Parse ``eplusout.csv`` into outdoor, long-format zones, HVAC, facility."""
    path = Path(path)
    result = EplusTimeseries(path=path)
    if not path.is_file():
        return result

    with path.open(encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.reader(f)
        try:
            header_raw = next(reader)
        except StopIteration:
            return result
        headers = [_norm_header(h) for h in header_raw]
        header_display = [h.strip() for h in header_raw]

        i_date = _find_col(headers, "date") or 0
        i_oat = (
            _find_col(headers, "outdoor", "drybulb")
            or _find_col(headers, "site outdoor air drybulb")
            or _find_col(headers, "environment", "outdoor air drybulb")
        )
        zone_cols = _find_all(headers, "zone mean air temperature")
        # Exclude environment / outdoor false positives
        zone_cols = [
            (i, header_display[i])
            for i, _ in zone_cols
            if "outdoor" not in headers[i] and "environment" not in headers[i]
        ]
        i_fan = _find_col(headers, "fan electricity rate")
        i_cool = (
            _find_col(headers, "cooling coil total cooling rate")
            or _find_col(headers, "chiller electricity rate")
        )
        i_heat = (
            _find_col(headers, "heating coil heating rate")
            or _find_col(headers, "heating coil total heating rate")
            or _find_col(headers, "boiler heating rate")
        )
        i_elec_fac = None
        i_gas_fac = None
        for i, h in enumerate(headers):
            if "electricity:facility" in h and i_elec_fac is None:
                i_elec_fac = i
            if ("naturalgas:facility" in h or "gas:facility" in h) and i_gas_fac is None:
                i_gas_fac = i

        result.columns_discovered = {
            "outdoor_drybulb": [header_display[i_oat]] if i_oat is not None else [],
            "zone_mean_air_temp": [h for _, h in zone_cols],
            "fan": [header_display[i_fan]] if i_fan is not None else [],
            "cooling": [header_display[i_cool]] if i_cool is not None else [],
            "heating": [header_display[i_heat]] if i_heat is not None else [],
            "facility_elec": [header_display[i_elec_fac]] if i_elec_fac is not None else [],
            "facility_gas": [header_display[i_gas_fac]] if i_gas_fac is not None else [],
        }

        outdoor_rows: list[dict[str, Any]] = []
        zone_rows: list[dict[str, Any]] = []
        hvac_rows: list[dict[str, Any]] = []
        facility_rows: list[dict[str, Any]] = []

        for row_i, raw in enumerate(reader):
            if not raw:
                continue
            ts = raw[i_date].strip() if i_date < len(raw) else str(row_i)

            def _f(idx: int | None) -> float:
                if idx is None or idx >= len(raw):
                    return float("nan")
                return _parse_float(raw[idx])

            oat = _f(i_oat)
            outdoor_rows.append({"timestamp": ts, "outdoor_db_c": oat})

            for idx, disp in zone_cols:
                zone_rows.append(
                    {
                        "timestamp": ts,
                        "zone": _zone_name_from_header(disp),
                        "temp_c": _f(idx),
                    }
                )

            hvac_rows.append(
                {
                    "timestamp": ts,
                    "fan_w": _f(i_fan),
                    "cooling_w": _f(i_cool),
                    "heating_w": _f(i_heat),
                }
            )
            facility_rows.append(
                {
                    "timestamp": ts,
                    "electricity_j": _f(i_elec_fac),
                    "natural_gas_j": _f(i_gas_fac),
                }
            )

    result.outdoor = pd.DataFrame(outdoor_rows)
    result.zones = pd.DataFrame(zone_rows)
    result.hvac = pd.DataFrame(hvac_rows)
    result.facility = pd.DataFrame(facility_rows)
    return result


def downsample_frame(df: pd.DataFrame, max_points: int = DEFAULT_UI_MAX_POINTS) -> pd.DataFrame:
    """Stride-downsample a DataFrame for Plotly UI responsiveness."""
    if df.empty or max_points <= 0 or len(df) <= max_points:
        return df
    stride = max(1, len(df) // max_points)
    return df.iloc[::stride].reset_index(drop=True)


def load_sim_timeseries(sim_dir: Path | str) -> EplusTimeseries | None:
    """Locate and parse eplusout.csv under a simulation output directory."""
    path = find_eplusout_csv(sim_dir)
    if path is None:
        return None
    return parse_eplusout_timeseries(path)
