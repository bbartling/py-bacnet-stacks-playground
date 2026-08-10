"""Load-profile analytics bound to ``SiteUiBundle`` (actual BAS vs W2A dial).

Closeness formula matches archived GL14 notebook:
``closeness% = max(0, 100 - |sim-obs|/obs * 100)``.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from eplus_gym_app.site_bundle import SiteUiBundle

SHAPE_SEGMENTS: dict[str, tuple[int, int]] = {
    "Base load": (0, 5),
    "Morning ramp": (5, 9),
    "Afternoon": (9, 16),
    "Evening setback": (16, 24),
}

DIAL_COLORS = {
    "Actual": "#1f2a30",
    "E20": "#2a9d8f",
    "SC02": "#e9c46a",
    "R02": "#f4a261",
    "A04": "#e76f51",
}


def load_bas_demand_oat(
    bundle: SiteUiBundle | None = None, *, csv_path: Path | None = None
) -> pd.DataFrame:
    """Hourly BAS demand × OAT from bundle CSV or an explicit picker path."""
    path = Path(csv_path) if csv_path else None
    if path is None:
        if bundle is None:
            raise ValueError("bundle or csv_path required")
        path = bundle.bas_demand_oat_csv
    df = pd.read_csv(path)
    # Normalize common interval / hourly shapes to hour_utc, kw_avg, oat_f
    colmap = {c.lower(): c for c in df.columns}
    if "hour_utc" not in df.columns:
        for alt in ("timestamp_utc", "timestamp", "time", "datetime"):
            if alt in colmap:
                df = df.rename(columns={colmap[alt]: "hour_utc"})
                break
    if "kw_avg" not in df.columns:
        for alt in ("facility_kw", "kw", "demand_kw", "kw_demand", "kw_avg"):
            if alt in colmap:
                df = df.rename(columns={colmap[alt]: "kw_avg"})
                break
    if "oat_f" not in df.columns:
        for alt in ("oat_f", "oat", "temp_f", "outdoor_f"):
            if alt in colmap and colmap[alt] in df.columns:
                df = df.rename(columns={colmap[alt]: "oat_f"})
                break
        if "oat_f" not in df.columns:
            df["oat_f"] = float("nan")

    need = {"hour_utc", "kw_avg"}
    missing = need - set(df.columns)
    if missing:
        raise ValueError(
            f"interval/demand CSV {path} missing columns {sorted(missing)}; "
            "need hour_utc (or timestamp) + kw_avg (or facility_kw)"
        )
    out = df.copy()
    out["hour_utc"] = pd.to_datetime(out["hour_utc"], utc=True, errors="coerce")
    out["kw_avg"] = pd.to_numeric(out["kw_avg"], errors="coerce")
    out["oat_f"] = pd.to_numeric(out["oat_f"], errors="coerce")
    if "day_type" not in out.columns:
        local = out["hour_utc"].dt.tz_convert("America/Chicago")
        out["day_type"] = np.where(local.dt.dayofweek < 5, "Weekday", "Weekend")
    out["local_day"] = (
        out["hour_utc"].dt.tz_convert("America/Chicago").dt.strftime("%Y-%m-%d")
    )
    out["hod"] = out["hour_utc"].dt.tz_convert("America/Chicago").dt.hour + (
        out["hour_utc"].dt.tz_convert("America/Chicago").dt.minute / 60.0
    )
    out = out.dropna(subset=["hour_utc", "kw_avg"]).sort_values("hour_utc")
    # Sub-hourly interval → hourly mean for period charts
    if len(out) >= 3:
        dt = out["hour_utc"].diff().dt.total_seconds().median()
        if dt is not None and dt == dt and dt < 1200:
            out = out.set_index("hour_utc")
            agg = {"kw_avg": "mean", "oat_f": "mean"}
            hourly = out.resample("h").agg(agg).dropna(subset=["kw_avg"]).reset_index()
            hourly["day_type"] = np.where(
                hourly["hour_utc"].dt.tz_convert("America/Chicago").dt.dayofweek < 5,
                "Weekday",
                "Weekend",
            )
            hourly["local_day"] = (
                hourly["hour_utc"]
                .dt.tz_convert("America/Chicago")
                .dt.strftime("%Y-%m-%d")
            )
            hourly["hod"] = hourly["hour_utc"].dt.tz_convert(
                "America/Chicago"
            ).dt.hour.astype(float)
            out = hourly
    return out


def find_peak_demand_day(bas: pd.DataFrame) -> tuple[str, float, pd.Timestamp]:
    """Return (local_day, peak_kw, peak_ts_utc) from BAS hourly frame."""
    if bas.empty:
        raise ValueError("empty BAS demand frame")
    idx = bas["kw_avg"].idxmax()
    row = bas.loc[idx]
    return str(row["local_day"]), float(row["kw_avg"]), pd.Timestamp(row["hour_utc"])


def peak_day_bas_profile(bas: pd.DataFrame, day: str) -> pd.DataFrame:
    sub = bas.loc[bas["local_day"] == day, ["hod", "kw_avg", "oat_f"]].copy()
    return sub.sort_values("hod")


def load_closeness_table(bundle: SiteUiBundle) -> pd.DataFrame:
    """Prefer precomputed closeness CSV declared on the bundle."""
    path = bundle.dial_ladder.precomputed_closeness_csv
    if path is None or not path.is_file():
        return pd.DataFrame(
            columns=[
                "day_type",
                "model",
                "component",
                "closeness_pct",
                "pct_error",
                "obs_kw",
                "sim_kw",
            ]
        )
    df = pd.read_csv(path)
    return df


def closeness_pivot(closeness: pd.DataFrame, *, day_type: str) -> pd.DataFrame:
    sub = closeness.loc[
        closeness["day_type"].astype(str).str.lower() == day_type.lower()
    ].copy()
    if sub.empty:
        return pd.DataFrame()
    return (
        sub.pivot(index="component", columns="model", values="closeness_pct")
        .reindex(list(SHAPE_SEGMENTS) + ["Full-day"])
    )


def shape_closeness_from_hourly(
    hourly: pd.DataFrame, *, weekend: bool
) -> dict[str, dict[str, float]]:
    """Compute segment closeness from columns ``obs`` / ``sim`` indexed by hour 0–23.

    ``hourly`` must have columns hour (0-23), obs, sim — one row per hour mean.
    """
    if hourly.empty:
        return {}
    df = hourly.copy()
    if "hour" not in df.columns:
        raise ValueError("hourly needs hour column")
    out: dict[str, dict[str, float]] = {}
    for name, (h0, h1) in SHAPE_SEGMENTS.items():
        band = df.loc[(df["hour"] >= h0) & (df["hour"] < h1)]
        if band.empty:
            continue
        obs = float(band["obs"].mean())
        sim = float(band["sim"].mean())
        if obs == 0:
            continue
        pct_err = 100.0 * (sim - obs) / obs
        out[name] = {
            "closeness_pct": max(0.0, 100.0 - abs(pct_err)),
            "pct_error": pct_err,
            "obs_kw": obs,
            "sim_kw": sim,
        }
    obs_m = float(df["obs"].mean())
    sim_m = float(df["sim"].mean())
    if obs_m:
        mae = float(np.mean(np.abs(df["sim"] - df["obs"])))
        # Full-day uses MAE/obs*100 like the notebook for consistency with tables
        out["Full-day"] = {
            "closeness_pct": max(0.0, 100.0 - 100.0 * mae / obs_m),
            "pct_error": 100.0 * (sim_m - obs_m) / obs_m,
            "obs_kw": obs_m,
            "sim_kw": sim_m,
        }
    _ = weekend  # API parity with notebook signature
    return out


def _find_eplusout(sim_dir: Path) -> Path | None:
    direct = sim_dir / "eplusout.csv"
    if direct.is_file():
        return direct
    alts = sorted(sim_dir.glob("eplusout*.csv"))
    return alts[0] if alts else None


def _norm(h: str) -> str:
    return re.sub(r"\s+", " ", (h or "").strip().lower())


def facility_kw_for_day(sim_dir: Path, day: str) -> Optional[pd.DataFrame]:
    """Extract facility electric kW vs hour-of-day for a local civil day from eplusout.

    EnergyPlus Date/Time stamps are simulation-local (often CST without TZ).
    Prefer ``Electricity:Facility [J](Hourly)`` (J per hour → kW = J / 3.6e6).
    Returns columns ``hod``, ``simulated_kw`` or None if unavailable.
    """
    path = _find_eplusout(sim_dir)
    if path is None:
        return None
    try:
        _y, m, d = (int(x) for x in day.split("-"))
    except ValueError:
        return None
    # Strict MM/DD match — do NOT use loose "1/26" (matches 11/26 too).
    day_re = re.compile(
        rf"(?:^|[\s/])0*{m}/0*{d}(?:\s|$)",
        re.IGNORECASE,
    )
    # Also accept zero-padded " 01/26  07:00:00"
    day_re_pad = re.compile(rf"(?:^|\s){m:02d}/{d:02d}\s")

    with path.open(encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.reader(f)
        try:
            header_raw = next(reader)
        except StopIteration:
            return None
        headers = [_norm(h) for h in header_raw]
        i_date = next((i for i, h in enumerate(headers) if "date" in h), 0)
        # Prefer Hourly J column; avoid Timestep duplicate series.
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
        header_elec = headers[i_elec]
        is_joules = "[j]" in header_elec

        rows: list[dict[str, float]] = []
        for raw in reader:
            if not raw or i_date >= len(raw) or i_elec >= len(raw):
                continue
            stamp = raw[i_date].strip()
            if not (day_re_pad.search(stamp) or day_re.search(stamp)):
                continue
            token = (raw[i_elec] or "").strip()
            if not token:
                continue
            try:
                val = float(token)
            except ValueError:
                continue
            if is_joules:
                # Hourly meter: Joules integrated over the hour → mean kW
                kw = val / 3_600_000.0
            elif val > 5000:
                kw = val / 1000.0  # W → kW
            else:
                kw = val
            # EP hour-ending stamps (01:00 … 24:00). Align to Actual civil hour 0..23:
            # HE 01:00 covers 00:00–01:00 → hod 0; HE 24:00 → hod 23.
            hod = 0.0
            m_hm = re.search(r"(\d{1,2}):(\d{2})", stamp)
            if m_hm:
                hh = int(m_hm.group(1))
                mm = int(m_hm.group(2))
                he = hh + mm / 60.0
                hod = max(0.0, he - 1.0)
            rows.append({"hod": hod, "simulated_kw": kw})

    if not rows:
        return None
    df = pd.DataFrame(rows).sort_values("hod")
    # One point per hod if duplicates slipped through
    df = df.groupby("hod", as_index=False)["simulated_kw"].mean()
    return df


def dial_peak_day_overlay(bundle: SiteUiBundle) -> dict[str, Any]:
    """Build Actual + dial-model series for the bundle peak day."""
    bas = load_bas_demand_oat(bundle)
    day = bundle.dial_ladder.peak_day
    actual = peak_day_bas_profile(bas, day)
    if actual.empty:
        day, peak_kw, _ = find_peak_demand_day(bas)
        actual = peak_day_bas_profile(bas, day)
    else:
        peak_kw = float(actual["kw_avg"].max()) if not actual.empty else float("nan")

    series: dict[str, pd.DataFrame] = {
        "Actual": actual.rename(columns={"kw_avg": "kw"})
    }
    for pin in bundle.dial_ladder.models:
        if pin.sim_dir is None:
            continue
        sim = facility_kw_for_day(pin.sim_dir, day)
        if sim is not None and not sim.empty:
            series[pin.id] = sim.rename(columns={"simulated_kw": "kw"})

    return {
        "day": day,
        "peak_kw": peak_kw,
        "utility_peak_kw": bundle.dial_ladder.utility_peak_kw,
        "series": series,
        "honesty": bundle.honesty.get("dial_ladder", "W2A_PHYSICAL_DSM"),
        "bas_honesty": bundle.honesty.get("bas", "BAS_INTERVAL_METER"),
        "promote": False,
    }
