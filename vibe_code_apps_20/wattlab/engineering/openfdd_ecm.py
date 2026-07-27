"""Thin adapter: WattLab → ``open_fdd.ecm_engineering`` (PyPI ``open-fdd``).

Architecture target:

```text
Open-FDD evidence
      |
      +--> Open-FDD ECM engineering calculator/workbook
      |
      +--> Vibe 20 EnergyPlus model
                 |
                 +--> engineering vs EnergyPlus cross-check
```

This module is the temporary bridge while ``wattlab.bench.algorithms`` /
``wattlab.bench.esco`` / generic weather-bin helpers are migrated and deleted
only after parity tests pass. Do **not** move EnergyPlus-specific code into
Open-FDD. Keep WattLab ECM IDs / ``catalog.yaml`` stable.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

# ---------------------------------------------------------------------------
# Import surface (fail loudly if package missing — Dockerfile must install it)
# ---------------------------------------------------------------------------

from open_fdd.ecm_engineering import (  # noqa: F401
    ECMJob,
    OpenFDDECMWorkbook,
    calculate as _ofdd_calculate,
    create_workbook,
    crosscheck as engineering_crosscheck,
    list_calculators as _ofdd_list_calculators,
    npv as ofdd_npv,
    simple_payback as ofdd_simple_payback,
)
from open_fdd.ecm_engineering import bin_methods as ofdd_bin_methods
from open_fdd.ecm_engineering import weather as ofdd_weather
from open_fdd.ecm_engineering.weather import (
    OperatingSchedule as OfddOperatingSchedule,
    WeatherBins as OfddWeatherBins,
    hours_reduction_fraction as ofdd_hours_reduction_fraction,
    saturated_enthalpy_btu_lb as ofdd_sat_enthalpy_btu_lb,
)

__all__ = [
    "ECMJob",
    "OpenFDDECMWorkbook",
    "OfddOperatingSchedule",
    "OfddWeatherBins",
    "calculate",
    "create_workbook",
    "engineering_crosscheck",
    "list_calculators",
    "ofdd_hours_reduction_fraction",
    "ofdd_npv",
    "ofdd_sat_enthalpy_btu_lb",
    "ofdd_simple_payback",
    "openfdd_available",
    "scheduling_cooling_bins",
    "scheduling_fan_bins",
    "scheduling_heating_bins",
    "to_ofdd_bins",
    "to_ofdd_schedule",
]


def openfdd_available() -> bool:
    """True when the Open-FDD ECM package is importable (always after image build)."""
    return True


def list_calculators() -> list[str]:
    return _ofdd_list_calculators()


def calculate(name: str, inputs: dict[str, Any]) -> dict[str, Any]:
    """Run a registered Open-FDD calculator by name (dict-in / dict-out)."""
    return _ofdd_calculate(name, inputs)


# ---------------------------------------------------------------------------
# WattLab weather ↔ Open-FDD weather
# ---------------------------------------------------------------------------

def to_ofdd_schedule(data: Mapping[str, Any] | OfddOperatingSchedule) -> OfddOperatingSchedule:
    if isinstance(data, OfddOperatingSchedule):
        return data
    return OfddOperatingSchedule.from_dict(dict(data))


def to_ofdd_bins(
    bins: Any,
    *,
    source: str = "",
) -> OfddWeatherBins:
    """Convert WattLab ``WeatherBins`` / record list / Open-FDD bins → Open-FDD.

    WattLab rows use ``temp`` / ``mcwb`` / ``enthalpy``.
    Open-FDD rows use ``temp_f`` / ``wetbulb_f`` / ``enthalpy_btu_lb``.
    """
    if isinstance(bins, OfddWeatherBins):
        return bins

    rows: Sequence[Mapping[str, Any]]
    if hasattr(bins, "to_records"):
        rows = bins.to_records()
        source = source or str(getattr(bins, "source", "") or "")
    elif isinstance(bins, Mapping) and "rows" in bins:
        rows = list(bins["rows"])  # type: ignore[arg-type]
        source = source or str(bins.get("source", "") or "")
    elif isinstance(bins, Sequence):
        rows = bins  # type: ignore[assignment]
    else:
        raise TypeError(f"unsupported bins type: {type(bins)!r}")

    ofdd_rows: list[dict[str, Any]] = []
    for r in rows:
        temp = r.get("temp_f", r.get("temp"))
        if temp is None:
            raise ValueError("bin row missing temp / temp_f")
        row: dict[str, Any] = {"temp_f": float(temp)}
        if "shift_hours" in r:
            row["shift_hours"] = list(r["shift_hours"])
        elif "hours" in r:
            row["hours"] = float(r["hours"])
        else:
            raise ValueError("bin row needs shift_hours or hours")
        wb = r.get("wetbulb_f", r.get("mcwb"))
        if wb is not None:
            row["wetbulb_f"] = float(wb)
        enh = r.get("enthalpy_btu_lb", r.get("enthalpy"))
        if enh is not None:
            row["enthalpy_btu_lb"] = float(enh)
        ofdd_rows.append(row)
    return OfddWeatherBins.from_rows(ofdd_rows, source=source)


def scheduling_fan_bins(inputs: Mapping[str, Any]) -> dict[str, Any]:
    """Open-FDD ``scheduling_fan_bins`` with WattLab-shaped schedule/bins inputs."""
    fan_kw = float(inputs["fan_kw_total"]) if "fan_kw_total" in inputs else sum(
        float(u.get("fan_kw", 0.0)) for u in inputs.get("units", [])
    )
    out = ofdd_bin_methods.scheduling_fan_bins(
        fan_kw_total=fan_kw,
        existing_schedule=to_ofdd_schedule(inputs["existing_schedule"]),
        proposed_schedule=to_ofdd_schedule(inputs["proposed_schedule"]),
        bins=to_ofdd_bins(inputs["bins"]),
    )
    return _normalize_scheduling_fan_result(out)


def scheduling_cooling_bins(inputs: Mapping[str, Any]) -> dict[str, Any]:
    supply_h = float(inputs.get("supply_enthalpy", inputs.get("supply_enthalpy_btu_lb", 23.2)))
    oa_cfm = float(inputs["oa_cfm_total"])
    kw_per_ton = float(inputs["kw_per_ton"])
    out = ofdd_bin_methods.scheduling_cooling_bins(
        oa_cfm_total=oa_cfm,
        kw_per_ton=kw_per_ton,
        existing_schedule=to_ofdd_schedule(inputs["existing_schedule"]),
        proposed_schedule=to_ofdd_schedule(inputs["proposed_schedule"]),
        bins=to_ofdd_bins(inputs["bins"]),
        supply_enthalpy_btu_lb=supply_h,
    )
    return _normalize_scheduling_cooling_result(out, oa_cfm=oa_cfm, supply_h=supply_h, kw_per_ton=kw_per_ton, inputs=inputs)


def scheduling_heating_bins(inputs: Mapping[str, Any]) -> dict[str, Any]:
    oa_cfm = float(inputs["oa_cfm_total"])
    balance = float(inputs.get("balance_point_f", 55.0))
    out = ofdd_bin_methods.scheduling_heating_bins(
        oa_cfm_total=oa_cfm,
        boiler_efficiency=float(inputs.get("boiler_efficiency", 0.8)),
        existing_schedule=to_ofdd_schedule(inputs["existing_schedule"]),
        proposed_schedule=to_ofdd_schedule(inputs["proposed_schedule"]),
        bins=to_ofdd_bins(inputs["bins"]),
        balance_point_f=balance,
    )
    return _normalize_scheduling_heating_result(out, oa_cfm=oa_cfm, balance_point_f=balance, inputs=inputs)


def _normalize_scheduling_fan_result(out: dict[str, Any]) -> dict[str, Any]:
    details = []
    for row in out.get("bins") or []:
        details.append({
            "temp": row.get("temp", row.get("temp_f")),
            "operating_hours": row.get("operating_hours"),
            "existing_kwh": row.get("existing_kwh", row.get("baseline_kwh")),
            "saved_kwh": row.get("saved_kwh"),
        })
    out = dict(out)
    out["bins"] = details
    return out


def _normalize_scheduling_cooling_result(
    out: dict[str, Any],
    *,
    oa_cfm: float,
    supply_h: float,
    kw_per_ton: float,
    inputs: Mapping[str, Any],
) -> dict[str, Any]:
    """Remap Open-FDD detail keys + reconstruct vent_cooling_ton_hr for WattLab goldens."""
    ofdd_bins = to_ofdd_bins(inputs["bins"])
    existing = to_ofdd_schedule(inputs["existing_schedule"])
    reduction = float(out.get("hours_reduction_fraction") or ofdd_hours_reduction_fraction(
        existing, to_ofdd_schedule(inputs["proposed_schedule"])
    ))
    details = []
    for row in ofdd_bins.rows:
        op_hours = existing.total_operating_hours(row.shift_hours)
        oa_h = row.oa_enthalpy
        ton_hr = 0.0 if oa_h is None or oa_h < supply_h else oa_cfm * (oa_h - supply_h) * 4.5 / 12000.0
        existing_kwh = ton_hr * op_hours * kw_per_ton
        details.append({
            "temp": row.temp_f,
            "operating_hours": op_hours,
            "vent_cooling_ton_hr": ton_hr,
            "existing_kwh": existing_kwh,
            "saved_kwh": existing_kwh * reduction,
        })
    out = dict(out)
    out["bins"] = details
    out.setdefault("hours_reduction_fraction", reduction)
    return out


def _normalize_scheduling_heating_result(
    out: dict[str, Any],
    *,
    oa_cfm: float,
    balance_point_f: float,
    inputs: Mapping[str, Any],
) -> dict[str, Any]:
    ofdd_bins = to_ofdd_bins(inputs["bins"])
    existing = to_ofdd_schedule(inputs["existing_schedule"])
    proposed = to_ofdd_schedule(inputs["proposed_schedule"])
    reduction = float(out.get("hours_reduction_fraction") or ofdd_hours_reduction_fraction(existing, proposed))
    efficiency = float(inputs.get("boiler_efficiency", 0.8))
    details = []
    for row in ofdd_bins.rows:
        op_hours = existing.total_operating_hours(row.shift_hours)
        load_kbtu_h = 0.0 if balance_point_f < row.temp_f else (balance_point_f - row.temp_f) * oa_cfm * 1.08 / 1000.0
        existing_mmbtu = load_kbtu_h * op_hours / efficiency / 1000.0
        details.append({
            "temp": row.temp_f,
            "operating_hours": op_hours,
            "vent_heat_kbtu_hr": load_kbtu_h,
            "existing_mmbtu": existing_mmbtu,
            "saved_mmbtu": existing_mmbtu * reduction,
        })
    out = dict(out)
    out["bins"] = details
    out.setdefault("hours_reduction_fraction", reduction)
    return out
