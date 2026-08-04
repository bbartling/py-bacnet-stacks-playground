"""Synthetic heating DSM action vectors + physics-ish facility_kw perturbations.

Provenance: BAS_BOOTSTRAP_PROXY — not EnergyPlus. Replace with E+ farm later
using the same FEATURE_COLS / strategy_id vocabulary.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from feature_compile_heating_dsm import OCC_FRAC_COLS, STRATEGY_IDS

# Zone short keys aligned with OCC_FRAC_COLS order
_ZONE_KEYS = ["1F_A", "1F_B", "1F_C", "1F_D", "2F_A", "2F_B"]


def _baseline_occ(hour_ending: int, *, weekday: bool) -> dict[str, float]:
    """Generic K12: unoccupied overnight, all zones on 07–16 weekdays."""
    if not weekday:
        return {k: 0.0 for k in _ZONE_KEYS}
    if 7 <= hour_ending < 16:
        return {k: 1.0 for k in _ZONE_KEYS}
    return {k: 0.0 for k in _ZONE_KEYS}


def _stagger_preheat_occ(hour_ending: int, *, weekday: bool, stagger_min: int = 30) -> dict[str, float]:
    """Spread morning wake-up: zones turn on 05:00–08:00 staggered, full by 08."""
    if not weekday:
        return {k: 0.0 for k in _ZONE_KEYS}
    if hour_ending >= 8 and hour_ending < 16:
        return {k: 1.0 for k in _ZONE_KEYS}
    if hour_ending < 5 or hour_ending >= 16:
        return {k: 0.0 for k in _ZONE_KEYS}
    # HE 5,6,7: progressive fractions
    step = max(1, stagger_min // 30)  # 1 zone-group per half-hour-ish
    n_on = min(6, max(0, (hour_ending - 4) * step))
    out = {k: 0.0 for k in _ZONE_KEYS}
    for i, k in enumerate(_ZONE_KEYS):
        out[k] = 1.0 if i < n_on else (0.35 if hour_ending == 7 and i < n_on + 2 else 0.0)
    if hour_ending == 7:
        for k in _ZONE_KEYS:
            out[k] = max(out[k], 0.85)
    return out


def _flat_24_7_occ(_hour_ending: int, **_kw: Any) -> dict[str, float]:
    return {k: 1.0 for k in _ZONE_KEYS}


def _deep_setback_occ(hour_ending: int, *, weekday: bool) -> dict[str, float]:
    """Aggressive night setback: zones off until 06:30-ish then hard on."""
    if not weekday:
        return {k: 0.0 for k in _ZONE_KEYS}
    if hour_ending < 7:
        return {k: 0.0 for k in _ZONE_KEYS}
    if hour_ending < 16:
        return {k: 1.0 for k in _ZONE_KEYS}
    return {k: 0.0 for k in _ZONE_KEYS}


def _morning_all_on_occ(hour_ending: int, *, weekday: bool) -> dict[str, float]:
    """Worst-case simultaneous morning startup from HE 5."""
    if not weekday:
        return {k: 0.0 for k in _ZONE_KEYS}
    if 5 <= hour_ending < 16:
        return {k: 1.0 for k in _ZONE_KEYS}
    return {k: 0.0 for k in _ZONE_KEYS}


_STRATEGY_OCC = {
    "baseline": lambda he, weekday: _baseline_occ(he, weekday=weekday),
    "stagger_preheat": lambda he, weekday: _stagger_preheat_occ(he, weekday=weekday, stagger_min=30),
    "flat_24_7": lambda he, weekday: _flat_24_7_occ(he),
    "deep_setback": lambda he, weekday: _deep_setback_occ(he, weekday=weekday),
    "morning_all_on": lambda he, weekday: _morning_all_on_occ(he, weekday=weekday),
}

_STRATEGY_KNOBS = {
    "baseline": {"preheat_lead_h": 0.0, "stagger_min": 0.0, "unocc_htg_sp_f": 65.0, "occ_htg_sp_f": 68.0},
    "stagger_preheat": {"preheat_lead_h": 2.0, "stagger_min": 30.0, "unocc_htg_sp_f": 64.0, "occ_htg_sp_f": 68.0},
    "flat_24_7": {"preheat_lead_h": 0.0, "stagger_min": 0.0, "unocc_htg_sp_f": 68.0, "occ_htg_sp_f": 68.0},
    "deep_setback": {"preheat_lead_h": 0.0, "stagger_min": 0.0, "unocc_htg_sp_f": 60.0, "occ_htg_sp_f": 68.0},
    "morning_all_on": {"preheat_lead_h": 2.0, "stagger_min": 0.0, "unocc_htg_sp_f": 62.0, "occ_htg_sp_f": 68.0},
}


def physics_proxy_kw(
    bas_kw: float,
    *,
    oat_f: float,
    hour_ending: int,
    weekday: bool,
    strategy_id: str,
    occ: dict[str, float],
    knobs: dict[str, float],
) -> float:
    """Heuristic delta vs observed BAS kW under alternate occupancy / setpoints.

    Heating load ∝ HDD × concurrent wake-up; 24/7 raises base; deep setback
    lowers night but spikes morning. Not a calibrated model — bootstrap only.
    """
    hdd = max(0.0, 65.0 - float(oat_f))
    sum_occ = float(sum(occ.values()))
    base_occ = _baseline_occ(hour_ending, weekday=weekday)
    base_sum = float(sum(base_occ.values()))

    # Concurrent heating intensity relative to baseline schedule
    delta_occ = sum_occ - base_sum
    morning = 5 <= hour_ending <= 9
    night = hour_ending < 5 or hour_ending >= 20

    # Scale heating-sensitive portion of load (~40–70% in winter HDD days)
    heat_share = 0.25 + 0.55 * min(1.0, hdd / 40.0)
    heat_kw = float(bas_kw) * heat_share
    other_kw = float(bas_kw) - heat_kw

    # Concurrent zone start penalty (kW per zone-equivalent × HDD factor)
    concurrent_pen = 0.0
    if morning and weekday:
        concurrent_pen = 4.5 * sum_occ * (0.4 + hdd / 50.0)
        if strategy_id == "stagger_preheat":
            concurrent_pen *= 0.55  # stagger softens peak
        if strategy_id == "morning_all_on":
            concurrent_pen *= 1.35
        if strategy_id == "deep_setback" and hour_ending in (7, 8):
            concurrent_pen *= 1.5  # recovery spike

    # Night setback / 24-7 base shift
    setback_delta = 0.0
    if night:
        sp_delta = 65.0 - float(knobs.get("unocc_htg_sp_f", 65.0))
        setback_delta = -0.8 * sp_delta * (0.3 + hdd / 40.0)  # lower SP → less kW
        if strategy_id == "flat_24_7":
            setback_delta = 6.0 * (0.4 + hdd / 45.0)  # always-on zones

    # Occupancy-driven heat relative to baseline
    occ_scale = 1.0 + 0.12 * delta_occ
    heat_adj = heat_kw * occ_scale + concurrent_pen + setback_delta

    out = other_kw + heat_adj
    return float(max(8.0, out))


def expand_day_with_strategies(
    day_df: pd.DataFrame,
    *,
    strategies: list[str] | None = None,
) -> pd.DataFrame:
    """Take one calendar day's BAS hourly rows → multi-strategy proxy rows."""
    strategies = strategies or list(STRATEGY_IDS)
    rows: list[dict[str, Any]] = []
    day = str(day_df["day"].iloc[0])
    weekday = bool(int(day_df["is_weekend"].iloc[0]) == 0)

    for sid in strategies:
        knobs = dict(_STRATEGY_KNOBS[sid])
        for _, r in day_df.iterrows():
            he = int(r["hour_ending"])
            occ = _STRATEGY_OCC[sid](he, weekday)
            bas_kw = float(r["facility_kw_bas"])
            oat = float(r["oat_f"])
            if sid == "baseline":
                kw = bas_kw
            else:
                kw = physics_proxy_kw(
                    bas_kw,
                    oat_f=oat,
                    hour_ending=he,
                    weekday=weekday,
                    strategy_id=sid,
                    occ=occ,
                    knobs=knobs,
                )
            row = {
                "day": day,
                "simulation_id": f"{day}__{sid}",
                "hour_ending": he,
                "month": int(r["month"]),
                "doy": int(r["doy"]),
                "is_weekend": float(r["is_weekend"]),
                "occupied": float(r["occupied"]),
                "oat_f": oat,
                "rh_pct": float(r.get("rh_pct", 50.0)),
                "ghi": float(r.get("ghi", 0.0)),
                "strategy_id": sid,
                "facility_kw": kw,
                "facility_kw_bas": bas_kw,
                "provenance": "BAS_BOOTSTRAP_PROXY",
                **knobs,
            }
            for col, key in zip(OCC_FRAC_COLS, _ZONE_KEYS):
                row[col] = float(occ[key])
            rows.append(row)
    return pd.DataFrame(rows)


__all__ = [
    "STRATEGY_IDS",
    "expand_day_with_strategies",
    "physics_proxy_kw",
]
