"""Weather-Man style OAT bin tables for ESCO bin-method calculators.

The source ESCO workbook spreadsheets drive every bin-method ECM from a "Weather Man"
table: 5 F outdoor-air temperature bins x three daily shifts (12am-8am,
8am-4pm, 4pm-12am) plus the mean-coincident wet bulb (MCWB) per bin.

This module provides:

- :class:`BinRow` / :class:`WeatherBins` — the bin table model, buildable from
  NOAA-style rows, from an hourly OAT series (e.g. the vibe19 dump's
  ``weather_observed.csv``), or the built-in Washington DC NOAA table used by
  the source workbooks.
- :class:`OperatingSchedule` — shift hours/week schedule with the
  spreadsheets' shift-weighting rule and override allowance.
- Saturation enthalpy psychrometrics (``sat_enthalpy_btu_lb``) used for the
  ventilation cooling load columns.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

SHIFT_LABELS = ("12am-8am", "8am-4pm", "4pm-12am")
P_ATM_PSIA = 14.696


# ---------------------------------------------------------------------------
# Psychrometrics
# ---------------------------------------------------------------------------

def saturation_pressure_psia(t_f: float) -> float:
    """Saturation pressure over liquid water (ASHRAE Hyland-Wexler), T in F."""
    t_r = t_f + 459.67
    ln_p = (
        -1.0440397e4 / t_r
        - 1.129465e1
        - 2.7022355e-2 * t_r
        + 1.289036e-5 * t_r**2
        - 2.4780681e-9 * t_r**3
        + 6.5459673 * math.log(t_r)
    )
    return math.exp(ln_p)


def sat_enthalpy_btu_lb(twb_f: float) -> float:
    """Enthalpy of saturated moist air at wet-bulb ``twb_f`` (Btu/lb dry air).

    This is the "Enthalpy Btu/lb" column of the Weather Man / scheduling
    sheets (enthalpy along the saturation curve at the bin MCWB). Agrees with
    the spreadsheet values within ~0.2 Btu/lb.
    """
    p_ws = saturation_pressure_psia(twb_f)
    w = 0.621945 * p_ws / (P_ATM_PSIA - p_ws)
    return 0.240 * twb_f + w * (1061.0 + 0.444 * twb_f)


# ---------------------------------------------------------------------------
# Operating schedules
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OperatingSchedule:
    """Daily-shift operating schedule as used by the source workbook bin sheets.

    ``shifts`` are the operating hours inside each 8-hour shift
    (12am-8am, 8am-4pm, 4pm-12am); ``days_per_week`` scales to a week.
    ``override_allowance`` inflates weekly hours (the sheets apply a 10%
    allowance for overrides on *proposed* schedules).
    """

    shifts: tuple[float, float, float]
    days_per_week: float
    override_allowance: float = 0.0

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "OperatingSchedule":
        shifts = tuple(float(x) for x in d["shifts"])
        if len(shifts) != 3:
            raise ValueError("schedule 'shifts' must have exactly 3 entries (12am-8am, 8am-4pm, 4pm-12am)")
        return cls(
            shifts=shifts,  # type: ignore[arg-type]
            days_per_week=float(d["days_per_week"]),
            override_allowance=float(d.get("override_allowance", 0.0)),
        )

    @property
    def weekly_hours(self) -> float:
        return sum(self.shifts) * self.days_per_week * (1.0 + self.override_allowance)

    def operating_bin_hours(self, shift_hours: Sequence[float]) -> tuple[float, float, float]:
        """Spreadsheet shift weighting: ``bin_hours * shift/8 * days/7`` per shift."""
        return tuple(
            float(shift_hours[i]) * self.shifts[i] / 8.0 * self.days_per_week / 7.0
            for i in range(3)
        )  # type: ignore[return-value]

    def total_operating_hours(self, shift_hours: Sequence[float]) -> float:
        return sum(self.operating_bin_hours(shift_hours))


def hours_reduction_fraction(existing: OperatingSchedule, proposed: OperatingSchedule) -> float:
    """``(existing_weekly - proposed_weekly) / existing_weekly`` (sheet column N)."""
    ew = existing.weekly_hours
    if ew <= 0:
        return 0.0
    return (ew - proposed.weekly_hours) / ew


# ---------------------------------------------------------------------------
# Weather bins
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BinRow:
    """One 5 F outdoor-air temperature bin."""

    temp: float
    """Bin midpoint temperature (F)."""
    shift_hours: tuple[float, float, float]
    """Annual hours in the bin per shift (12am-8am, 8am-4pm, 4pm-12am)."""
    mcwb: float | None = None
    """Mean coincident wet bulb (F)."""
    enthalpy: float | None = None
    """Optional explicit OA enthalpy (Btu/lb) overriding the MCWB curve."""

    @property
    def annual_hours(self) -> float:
        return sum(self.shift_hours)

    @property
    def oa_enthalpy(self) -> float | None:
        if self.enthalpy is not None:
            return self.enthalpy
        if self.mcwb is not None:
            return sat_enthalpy_btu_lb(self.mcwb)
        return None


@dataclass(frozen=True)
class WeatherBins:
    """Weather-Man style OAT bin table (hot -> cold)."""

    rows: tuple[BinRow, ...]
    source: str = ""
    notes: str = ""

    @property
    def total_hours(self) -> float:
        return sum(r.annual_hours for r in self.rows)

    def to_records(self) -> list[dict[str, Any]]:
        return [
            {
                "temp": r.temp,
                "shift_hours": list(r.shift_hours),
                "mcwb": r.mcwb,
                "enthalpy": r.enthalpy,
                "annual_hours": r.annual_hours,
            }
            for r in self.rows
        ]

    @classmethod
    def from_rows(cls, rows: Iterable[dict[str, Any]], source: str = "", notes: str = "") -> "WeatherBins":
        """Build from dict rows: ``{"temp", "shift_hours" | "hours", "mcwb"?, "enthalpy"?}``.

        ``hours`` (a single annual total) is split across shifts as 1/3 each
        when per-shift hours are not known.
        """
        out: list[BinRow] = []
        for r in rows:
            if "shift_hours" in r:
                sh = tuple(float(x) for x in r["shift_hours"])
                if len(sh) != 3:
                    raise ValueError("shift_hours must have 3 entries")
            elif "hours" in r:
                h = float(r["hours"]) / 3.0
                sh = (h, h, h)
            else:
                raise ValueError("bin row needs 'shift_hours' or 'hours'")
            out.append(
                BinRow(
                    temp=float(r["temp"]),
                    shift_hours=sh,  # type: ignore[arg-type]
                    mcwb=None if r.get("mcwb") is None else float(r["mcwb"]),
                    enthalpy=None if r.get("enthalpy") is None else float(r["enthalpy"]),
                )
            )
        out.sort(key=lambda r: r.temp, reverse=True)
        return cls(rows=tuple(out), source=source, notes=notes)

    @classmethod
    def from_hourly(
        cls,
        timestamps: Sequence[Any],
        oat_f: Sequence[float],
        wetbulb_f: Sequence[float] | None = None,
        bin_width: float = 5.0,
        source: str = "hourly",
    ) -> "WeatherBins":
        """Bin an hourly OAT series (e.g. vibe19 ``weather_observed.csv``).

        Timestamps may be datetimes or anything pandas can parse. Shifts follow
        the spreadsheet convention (hour 0-7, 8-15, 16-23). When a coincident
        wet-bulb series is supplied, per-bin MCWB is its mean within the bin.
        """
        import pandas as pd

        ts = pd.to_datetime(pd.Series(list(timestamps)), errors="coerce")
        oat = pd.to_numeric(pd.Series(list(oat_f)), errors="coerce")
        frame = pd.DataFrame({"ts": ts, "oat": oat})
        if wetbulb_f is not None:
            frame["wb"] = pd.to_numeric(pd.Series(list(wetbulb_f)), errors="coerce")
        frame = frame.dropna(subset=["ts", "oat"])
        if frame.empty:
            raise ValueError("no valid (timestamp, oat) samples to bin")

        frame["shift"] = frame["ts"].dt.hour // 8
        # Bin midpoints aligned like the NOAA table: ...,-3, 2, 7, ..., 102
        frame["bin_mid"] = ((frame["oat"] - 2.0) / bin_width).round(0) * bin_width + 2.0

        rows: list[BinRow] = []
        for mid, grp in frame.groupby("bin_mid"):
            counts = grp.groupby("shift").size()
            sh = tuple(float(counts.get(i, 0)) for i in range(3))
            mcwb = float(grp["wb"].mean()) if "wb" in grp and grp["wb"].notna().any() else None
            rows.append(BinRow(temp=float(mid), shift_hours=sh, mcwb=mcwb))  # type: ignore[arg-type]
        rows.sort(key=lambda r: r.temp, reverse=True)
        return cls(rows=tuple(rows), source=source, notes=f"binned from {len(frame)} hourly samples")


def washington_dc_noaa() -> WeatherBins:
    """The NOAA Washington DC bin table used by the source ESCO workbooks.

    5 F bins x three shifts (2920 h per shift) with per-bin MCWB, transcribed
    from the "Weather Man" sheet ("Data Compiled by NOAA for Washington, DC").
    """
    data = [
        # (temp, 12am-8am, 8am-4pm, 4pm-12am, mcwb)
        (102, 0, 0, 0, None),
        (97, 0, 42, 2, 73.5),
        (92, 0, 131, 21, 72.4),
        (87, 3, 317, 75, 71.0),
        (82, 27, 302, 181, 70.4),
        (77, 126, 217, 268, 69.3),
        (72, 322, 211, 295, 67.0),
        (67, 335, 164, 250, 63.1),
        (62, 300, 150, 223, 58.7),
        (57, 180, 253, 178, 53.4),
        (52, 185, 216, 213, 48.7),
        (47, 195, 227, 189, 44.0),
        (42, 230, 230, 252, 39.7),
        (37, 283, 192, 257, 35.4),
        (32, 324, 114, 224, 30.8),
        (27, 211, 75, 156, 25.9),
        (22, 120, 67, 81, 20.2),
        (17, 53, 12, 53, 15.7),
        (12, 22, 0, 2, 12.3),
        (7, 4, 0, 0, 8.4),
        (2, 0, 0, 0, None),
        (-3, 0, 0, 0, None),
        (-8, 0, 0, 0, None),
    ]
    rows = tuple(
        BinRow(temp=float(t), shift_hours=(float(a), float(b), float(c)), mcwb=m)
        for t, a, b, c, m in data
    )
    return WeatherBins(rows=rows, source="NOAA Washington DC", notes="source workbook Weather Man table")


def parse_bins_input(value: Any) -> WeatherBins:
    """Coerce calculator input into :class:`WeatherBins`.

    Accepts a :class:`WeatherBins`, a list of bin-row dicts, or the string
    ``"washington_dc"`` for the built-in NOAA table.
    """
    if isinstance(value, WeatherBins):
        return value
    if isinstance(value, str):
        if value.lower() in {"washington_dc", "washington dc", "dca", "noaa_dc"}:
            return washington_dc_noaa()
        raise ValueError(f"unknown named bin table: {value!r}")
    if isinstance(value, (list, tuple)):
        return WeatherBins.from_rows(value)
    raise ValueError("bins must be a WeatherBins, list of rows, or a named table")
