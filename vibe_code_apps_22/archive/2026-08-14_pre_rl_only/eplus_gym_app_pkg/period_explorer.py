"""BOPTEST-style period windows: Actual BAS vs selected dial E+ model."""
from __future__ import annotations

import csv
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional, Sequence

import numpy as np
import pandas as pd

from eplus_gym_app.load_profiles import (
    _find_eplusout,
    _norm,
    find_peak_demand_day,
    load_bas_demand_oat,
)
from eplus_gym_app.site_bundle import DialModelPin, ModelCatalogEntry, SiteUiBundle

PERIOD_PRESETS = (
    "Peak day",
    "Peak week",
    "Calendar month",
    "Winter (Dec-Feb)",
    "Calendar year",
)


def _parse_day(s: str) -> date:
    return date.fromisoformat(str(s)[:10])


def days_for_period(
    bas: pd.DataFrame,
    *,
    preset: str,
    peak_day: str,
    month: str | None = None,
) -> list[str]:
    """Return sorted YYYY-MM-DD list for the selected period."""
    available = sorted(bas["local_day"].astype(str).unique())
    avail_set = set(available)
    if not available:
        return []

    if peak_day not in avail_set:
        peak_day, _, _ = find_peak_demand_day(bas)

    pd0 = _parse_day(peak_day)

    if preset == "Peak day":
        wanted = [peak_day]
    elif preset == "Peak week":
        # Monday-start week containing peak day
        start = pd0 - timedelta(days=pd0.weekday())
        wanted = [(start + timedelta(days=i)).isoformat() for i in range(7)]
    elif preset == "Calendar month":
        ym = month or peak_day[:7]
        wanted = [d for d in available if d.startswith(ym)]
        if not wanted:
            # fall back to civil days in month even if BAS sparse
            y, m = int(ym[:4]), int(ym[5:7])
            if m == 12:
                n = 31
            else:
                n = (date(y, m + 1, 1) - timedelta(days=1)).day
            wanted = [date(y, m, d).isoformat() for d in range(1, n + 1)]
    elif preset == "Winter (Dec-Feb)":
        # Season ending in peak year's winter: Dec (y-1) + Jan-Feb (y)
        y = pd0.year if pd0.month >= 3 else pd0.year
        # If peak is Jan/Feb, winter is Dec(y-1)–Feb(y); if Dec peak, Dec(y)–Feb(y+1)
        if pd0.month == 12:
            dec_y, jan_y = pd0.year, pd0.year + 1
        else:
            dec_y, jan_y = pd0.year - 1, pd0.year
        wanted = [
            d
            for d in available
            if d.startswith(f"{dec_y}-12")
            or d.startswith(f"{jan_y}-01")
            or d.startswith(f"{jan_y}-02")
        ]
    elif preset == "Calendar year":
        y = str(pd0.year)
        wanted = [d for d in available if d.startswith(f"{y}-")]
        if not wanted:
            wanted = [
                date(pd0.year, 1, 1).isoformat(),
                date(pd0.year, 12, 31).isoformat(),
            ]
    else:
        wanted = [peak_day]

    # Prefer intersection with BAS when non-empty for multi-day presets
    if preset in ("Calendar month", "Winter (Dec-Feb)", "Peak week", "Calendar year"):
        inter = [d for d in wanted if d in avail_set]
        if inter:
            return inter
    return [d for d in wanted if d in avail_set] or (
        [peak_day] if peak_day in avail_set else available[:1]
    )


def bas_period_frame(bas: pd.DataFrame, days: Sequence[str]) -> pd.DataFrame:
    """BAS hourly rows for days with continuous ``t_hours`` from period start."""
    day_set = set(days)
    sub = bas.loc[bas["local_day"].astype(str).isin(day_set)].copy()
    if sub.empty:
        return sub
    sub = sub.sort_values("hour_utc")
    t0 = sub["hour_utc"].iloc[0]
    sub["t_hours"] = (sub["hour_utc"] - t0).dt.total_seconds() / 3600.0
    sub["kw"] = sub["kw_avg"]
    sub["series"] = "Actual"
    return sub


def _ep_stamp_md_hod(stamp: str) -> tuple[int, int, float] | None:
    """Parse EnergyPlus `` MM/DD  HH:MM:SS`` → (month, day, hod 0–23)."""
    m = re.search(
        r"(?P<mo>\d{1,2})/(?P<dy>\d{1,2})\s+(?P<hh>\d{1,2}):(?P<mm>\d{2})",
        stamp,
    )
    if not m:
        return None
    mo = int(m.group("mo"))
    dy = int(m.group("dy"))
    hh = int(m.group("hh"))
    mi = int(m.group("mm"))
    he = hh + mi / 60.0
    hod = max(0.0, he - 1.0)
    return mo, dy, hod


def facility_kw_for_days(
    sim_dir: Path, days: Sequence[str]
) -> Optional[pd.DataFrame]:
    """Hourly facility kW for many civil days from one eplusout (one pass)."""
    path = _find_eplusout(sim_dir)
    if path is None or not days:
        return None
    wanted: set[tuple[int, int]] = set()
    day_order: list[str] = []
    for d in days:
        try:
            y, m, dd = (int(x) for x in str(d)[:10].split("-"))
        except ValueError:
            continue
        wanted.add((m, dd))
        day_order.append(f"{y:04d}-{m:02d}-{dd:02d}")
    if not wanted:
        return None

    with path.open(encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.reader(f)
        try:
            header_raw = next(reader)
        except StopIteration:
            return None
        headers = [_norm(h) for h in header_raw]
        i_date = next((i for i, h in enumerate(headers) if "date" in h), 0)
        i_elec = None
        for i, h in enumerate(headers):
            if "electricity:facility" in h and "(hourly)" in h:
                i_elec = i
                break
        if i_elec is None:
            i_elec = next(
                (i for i, h in enumerate(headers) if "electricity:facility" in h),
                None,
            )
        if i_elec is None:
            return None
        is_joules = "[j]" in headers[i_elec]

        rows: list[dict[str, Any]] = []
        for raw in reader:
            if not raw or i_date >= len(raw) or i_elec >= len(raw):
                continue
            stamp = raw[i_date].strip()
            parsed = _ep_stamp_md_hod(stamp)
            if parsed is None:
                continue
            mo, dy, hod = parsed
            if (mo, dy) not in wanted:
                continue
            token = (raw[i_elec] or "").strip()
            if not token:
                continue
            try:
                val = float(token)
            except ValueError:
                continue
            kw = val / 3_600_000.0 if is_joules else (val / 1000.0 if val > 5000 else val)
            # Year unknown in EP stamp — tag as MM-DD only; map via day_order
            rows.append({"mo": mo, "dy": dy, "hod": hod, "kw": kw})

    if not rows:
        return None
    raw_df = pd.DataFrame(rows)
    # Attach civil day using first matching YYYY-MM-DD in day_order
    md_to_day: dict[tuple[int, int], str] = {}
    for d in day_order:
        y, m, dd = (int(x) for x in d.split("-"))
        md_to_day.setdefault((m, dd), d)
    raw_df["local_day"] = [
        md_to_day.get((int(r.mo), int(r.dy))) for r in raw_df.itertuples()
    ]
    raw_df = raw_df.dropna(subset=["local_day"])
    raw_df = (
        raw_df.groupby(["local_day", "hod"], as_index=False)["kw"].mean().sort_values(
            ["local_day", "hod"]
        )
    )
    # Continuous hours from first day 00:00
    day_index = {d: i for i, d in enumerate(sorted(raw_df["local_day"].unique()))}
    raw_df["t_hours"] = raw_df.apply(
        lambda r: day_index[r["local_day"]] * 24.0 + float(r["hod"]), axis=1
    )
    return raw_df.sort_values("t_hours")


def resolve_dial_sim(
    bundle: SiteUiBundle, active: ModelCatalogEntry | None
) -> DialModelPin | None:
    if active is None:
        return None
    dial_id = active.dial_id or (active.id if active.family == "W2A_PHYSICAL_DSM" else None)
    if not dial_id:
        return None
    for pin in bundle.dial_ladder.models:
        if pin.id == dial_id and pin.sim_dir is not None:
            return pin
    return None


def series_energy_kwh(df: pd.DataFrame | None, *, kw_col: str = "kw") -> float:
    """Integrate a kW series to kWh using median timestep (hours)."""
    if df is None or getattr(df, "empty", True) or kw_col not in df.columns:
        return float("nan")
    work = df.dropna(subset=[kw_col])
    if work.empty:
        return float("nan")
    dt_h = 1.0
    if "t_hours" in work.columns and len(work) >= 2:
        delta = work["t_hours"].astype(float).sort_values().diff().median()
        if delta is not None and delta == delta and float(delta) > 0:
            dt_h = float(delta)
    return float(work[kw_col].sum() * dt_h)


def _pct_off(sim: float, actual: float) -> float:
    if not np.isfinite(sim) or not np.isfinite(actual) or not actual:
        return float("nan")
    return 100.0 * (sim - actual) / actual


def locked_calibration_window(
    bas: pd.DataFrame,
    *,
    peak_day: str,
    last: dict[str, Any] | None,
    session_preset: str | None,
    session_month: str | None,
) -> dict[str, Any]:
    """Period for Calibration: last Run DSM window, else the Run DSM widgets."""
    if last:
        days = [str(d)[:10] for d in (last.get("window_days") or []) if d]
        preset = str(last.get("preset") or session_preset or "Peak day")
        month = session_month
        if preset == "Calendar month":
            if last.get("period"):
                month = str(last["period"])[:7]
            elif days:
                month = days[0][:7]
        if not days:
            days = days_for_period(
                bas, preset=preset, peak_day=str(last.get("day") or peak_day), month=month
            )
        if days:
            begin, end = days[0], days[-1]
            return {
                "preset": preset,
                "month": month,
                "days": days,
                "locked": True,
                "source": "last_dsm_run",
                "period": str(last.get("period") or f"{begin}/{end}"),
            }

    preset = str(session_preset or "Peak day")
    month = session_month
    days = days_for_period(bas, preset=preset, peak_day=peak_day, month=month)
    begin = days[0] if days else ""
    end = days[-1] if days else ""
    return {
        "preset": preset,
        "month": month,
        "days": days,
        "locked": False,
        "source": "run_dsm_widgets",
        "period": f"{begin}/{end}" if begin else "",
    }


def period_overlay(
    bundle: SiteUiBundle,
    active: ModelCatalogEntry | None,
    *,
    preset: str,
    month: str | None = None,
    bas_csv: Path | None = None,
    days: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Actual BAS + selected dial model for a BOPTEST-style period."""
    bas = load_bas_demand_oat(bundle, csv_path=bas_csv)
    peak_day = bundle.dial_ladder.peak_day
    day_list = [str(d)[:10] for d in days if d] if days else []
    if not day_list:
        day_list = days_for_period(bas, preset=preset, peak_day=peak_day, month=month)
    actual = bas_period_frame(bas, day_list)

    pin = resolve_dial_sim(bundle, active)
    sim_df: pd.DataFrame | None = None
    if pin and pin.sim_dir is not None:
        sim_df = facility_kw_for_days(pin.sim_dir, day_list)

    util = bundle.dial_ladder.utility_peak_kw
    actual_peak = float(actual["kw"].max()) if not actual.empty else float("nan")
    sim_peak = float(sim_df["kw"].max()) if sim_df is not None and not sim_df.empty else float("nan")
    actual_kwh = series_energy_kwh(actual)
    sim_kwh = series_energy_kwh(sim_df)
    pct_peak = _pct_off(sim_peak, actual_peak)
    pct_kwh = _pct_off(sim_kwh, actual_kwh)

    return {
        "preset": preset,
        "days": day_list,
        "n_days": len(day_list),
        "peak_day_anchor": peak_day,
        "actual": actual,
        "sim": sim_df,
        "sim_id": pin.id if pin else None,
        "model_id": active.id if active else None,
        "family": active.family if active else None,
        "utility_peak_kw": util,
        "actual_peak_kw": actual_peak,
        "sim_peak_kw": sim_peak,
        "actual_kwh": actual_kwh,
        "sim_kwh": sim_kwh,
        "pct_vs_actual": pct_peak,
        "pct_vs_actual_peak": pct_peak,
        "pct_vs_actual_kwh": pct_kwh,
        "honesty_bas": bundle.honesty.get("bas", "BAS_INTERVAL_METER"),
        "honesty_model": (
            active.family if active else bundle.honesty.get("dial_ladder", "W2A_PHYSICAL_DSM")
        ),
        "promote": False,
    }
