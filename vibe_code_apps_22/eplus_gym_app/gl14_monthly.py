"""Published-champion monthly utility bills vs EnergyPlus (GL14 fuel view)."""
from __future__ import annotations

import csv
import re
from calendar import monthrange
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from eplus_gym_app.period_explorer import resolve_dial_sim
from eplus_gym_app.site_bundle import ModelCatalogEntry, SiteUiBundle

_STAMP = re.compile(r"(?P<mo>\d{1,2})/(?P<dy>\d{1,2})\s+(?P<hh>\d{1,2}):")
_OBS_NAMES = (
    "observed_monthly_utility.csv",
    "utility_bills_monthly.csv",
)


def _civil_year(mo: int, peak_day: str) -> int:
    """Map E+ MM stamp onto the billing year around the pack peak day."""
    pd0 = date.fromisoformat(str(peak_day)[:10])
    if mo >= 8:
        return pd0.year - 1 if pd0.month < 8 else pd0.year
    return pd0.year if pd0.month < 8 else pd0.year + 1


def _find_mtr(sim_dir: Path) -> Path | None:
    for name in ("eplusmtr.csv", "eplusout.csv"):
        cand = Path(sim_dir) / name
        if cand.is_file():
            return cand
    return None


def observed_monthly_path(site: Path) -> Path | None:
    root = Path(site)
    for rel in (
        Path("reports") / "eplus" / "observed_monthly_utility.csv",
        Path("reports") / "observed_monthly_utility.csv",
        Path("eplus") / "reports" / "observed_monthly_utility.csv",
    ):
        cand = root / rel
        if cand.is_file():
            return cand
    for name in _OBS_NAMES:
        hits = list(root.joinpath("reports").rglob(name)) if (root / "reports").is_dir() else []
        if hits:
            return hits[0]
    return None


def load_observed_monthly(
    site: Path,
    *,
    campus_elec: pd.DataFrame | None = None,
    campus_fuel: pd.DataFrame | None = None,
    fuel: str = "electricity",
) -> pd.DataFrame:
    """Utility-bill months: ``month``, ``kwh_obs``, optional ``peak_kw_obs``.

    For electricity, prefers ``observed_monthly_utility.csv`` then campus bills.
    For gas, uses ``campus_fuel`` / ``campus_elec`` bill frames (usage as obs).
    """
    bills = campus_fuel if campus_fuel is not None else campus_elec
    fuel_l = (fuel or "electricity").strip().lower()
    if fuel_l in ("electricity", "elec", "electric"):
        path = observed_monthly_path(site)
        if path is not None:
            raw = pd.read_csv(path)
            cols = {str(c).strip().lower(): c for c in raw.columns}
            month_c = cols.get("month") or cols.get("yyyy-mm") or list(raw.columns)[0]
            kwh_c = (
                cols.get("kwh_obs")
                or cols.get("observed_kwh")
                or cols.get("kwh")
                or cols.get("usage")
            )
            peak_c = cols.get("peak_kw_obs") or cols.get("demand_kw") or cols.get("peak_kw")
            out = pd.DataFrame(
                {
                    "month": raw[month_c].astype(str).str.strip().str[:7],
                    "kwh_obs": pd.to_numeric(raw[kwh_c], errors="coerce")
                    if kwh_c
                    else float("nan"),
                }
            )
            if peak_c is not None:
                out["peak_kw_obs"] = pd.to_numeric(raw[peak_c], errors="coerce")
            return out.dropna(subset=["month"]).sort_values("month").reset_index(drop=True)

    if bills is not None and not bills.empty and "usage" in bills.columns:
        g = bills.groupby("month", as_index=False).agg(
            kwh_obs=("usage", "sum"),
            **(
                {"peak_kw_obs": ("demand_kw", "max")}
                if "demand_kw" in bills.columns
                else {}
            ),
        )
        g["month"] = g["month"].astype(str).str[:7]
        return g.sort_values("month").reset_index(drop=True)
    return pd.DataFrame(columns=["month", "kwh_obs"])


def _facility_meter_token(fuel: str) -> str:
    f = (fuel or "electricity").strip().lower()
    if f in ("gas", "natural_gas", "naturalgas", "ng"):
        return "naturalgas:facility"
    return "electricity:facility"


def monthly_sim_from_mtr(
    sim_dir: Path, *, peak_day: str, fuel: str = "electricity"
) -> pd.DataFrame:
    """Monthly facility energy + hourly peak from published ``eplusmtr.csv``.

    ``fuel`` selects Electricity:Facility (default) or NaturalGas:Facility.
    Gas values are reported as kWh-equivalent of the meter Joules column
    (same J→kWh conversion) so joins stay column-compatible with bills.
    """
    path = _find_mtr(sim_dir)
    empty = pd.DataFrame(columns=["month", "kwh_sim", "peak_kw_sim"])
    if path is None:
        return empty
    meter = _facility_meter_token(fuel)
    with path.open(encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.reader(fh)
        try:
            header = next(reader)
        except StopIteration:
            return empty
        headers = [re.sub(r"\s+", " ", (h or "").strip().lower()) for h in header]
        i_date = next((i for i, h in enumerate(headers) if "date" in h), 0)
        i_month = next(
            (
                i
                for i, h in enumerate(headers)
                if meter in h and "monthly" in h
            ),
            None,
        )
        i_hour = next(
            (
                i
                for i, h in enumerate(headers)
                if meter in h and "hourly" in h
            ),
            None,
        )
        monthly: dict[tuple[int, int], tuple[int, float]] = {}
        peaks: dict[str, float] = {}
        for raw in reader:
            if not raw or i_date >= len(raw):
                continue
            parsed = _STAMP.search((raw[i_date] or "").strip())
            if parsed is None:
                continue
            mo = int(parsed.group("mo"))
            dy = int(parsed.group("dy"))
            year = _civil_year(mo, peak_day)
            ym = f"{year:04d}-{mo:02d}"
            if i_month is not None and i_month < len(raw):
                tok = (raw[i_month] or "").strip()
                if tok:
                    try:
                        joules = float(tok)
                    except ValueError:
                        joules = None
                    if joules is not None:
                        prev = monthly.get((year, mo))
                        if prev is None or dy >= prev[0]:
                            monthly[(year, mo)] = (dy, joules / 3_600_000.0)
            if i_hour is not None and i_hour < len(raw):
                tok = (raw[i_hour] or "").strip()
                if tok:
                    try:
                        kw = float(tok) / 3_600_000.0
                    except ValueError:
                        kw = None
                    if kw is not None:
                        peaks[ym] = max(kw, peaks.get(ym, float("-inf")))

    rows: list[dict[str, Any]] = []
    for (year, mo), (dy, kwh) in sorted(monthly.items()):
        last = monthrange(year, mo)[1]
        if dy < min(28, last):
            continue
        ym = f"{year:04d}-{mo:02d}"
        peak = peaks.get(ym)
        rows.append(
            {
                "month": ym,
                "kwh_sim": float(kwh),
                "peak_kw_sim": float(peak) if peak not in (None, float("-inf")) else float("nan"),
            }
        )
    return pd.DataFrame(rows) if rows else empty


def champion_gl14_monthly(
    bundle: SiteUiBundle,
    active: ModelCatalogEntry | None,
    *,
    campus_elec: pd.DataFrame | None = None,
    campus_fuel: pd.DataFrame | None = None,
    fuel: str = "electricity",
) -> pd.DataFrame:
    """Join utility bills to published champion (or active dial) monthly E+."""
    obs = load_observed_monthly(
        bundle.site,
        campus_elec=campus_elec,
        campus_fuel=campus_fuel,
        fuel=fuel,
    )
    pin = resolve_dial_sim(bundle, active)
    sim = (
        monthly_sim_from_mtr(
            pin.sim_dir,
            peak_day=bundle.dial_ladder.peak_day,
            fuel=fuel,
        )
        if pin and pin.sim_dir is not None
        else pd.DataFrame(columns=["month", "kwh_sim", "peak_kw_sim"])
    )
    if obs.empty and sim.empty:
        return pd.DataFrame(
            columns=[
                "month",
                "kwh_obs",
                "kwh_sim",
                "pct_error",
                "peak_kw_obs",
                "peak_kw_sim",
            ]
        )
    if obs.empty:
        out = sim.copy()
        out["kwh_obs"] = float("nan")
        out["peak_kw_obs"] = float("nan")
    elif sim.empty:
        out = obs.copy()
        out["kwh_sim"] = float("nan")
        out["peak_kw_sim"] = float("nan")
    else:
        out = obs.merge(sim, on="month", how="outer")
    out["pct_error"] = (out["kwh_sim"] - out["kwh_obs"]) / out["kwh_obs"] * 100.0
    out["sim_id"] = pin.id if pin else (active.id if active else None)
    return out.sort_values("month").reset_index(drop=True)
