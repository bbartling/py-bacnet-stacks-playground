"""Extract IdealLoads+COP site electric proxy time series from eplusout/eplusmtr CSV."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from eplus_native.meters import site_electric_proxy_kw


def _find_col(columns: list[str], *needles: str) -> str | None:
    low = {c: c.lower() for c in columns}
    for c, lc in low.items():
        if all(n.lower() in lc for n in needles):
            return c
    return None


def load_timestep_proxy_kw(
    sim_dir: Path | str,
    *,
    heat_cop: float = 3.5,
    cool_cop: float = 4.5,
    interval_hours: float = 0.25,
    prefer_freq: str = "timestep",
) -> pd.DataFrame:
    """Build timestep site_electric_proxy_kw from meter CSV.

    Prefers ``(TimeStep)`` meter columns. Drops all-NaN rows and keeps finite kW only.
    """
    sim = Path(sim_dir)
    mtr = sim / "eplusmtr.csv"
    src = mtr if mtr.is_file() else sim / "eplusout.csv"
    if not src.is_file():
        raise FileNotFoundError(f"no meter/csv outputs in {sim}")
    df = pd.read_csv(src)
    cols = list(df.columns)
    ts_col = cols[0]
    freq = prefer_freq.lower()
    elec = _find_col(cols, "electricity:facility", freq) or _find_col(
        cols, "electricity:facility", "hourly"
    )
    dh = _find_col(cols, "districtheatingwater:facility", freq) or _find_col(
        cols, "districtheatingwater:facility", "hourly"
    )
    dc = _find_col(cols, "districtcooling:facility", freq) or _find_col(
        cols, "districtcooling:facility", "hourly"
    )
    if elec is None:
        elev = [c for c in cols if "Electricity:Facility" in c and "Monthly" not in c]
        elec = elev[0] if elev else None
    if elec is None:
        raise ValueError(f"Electricity:Facility column not found in {src.name}")

    rows = []
    for _, r in df.iterrows():
        stamp = str(r[ts_col]).strip()
        if not stamp or stamp.lower().startswith("date"):
            continue
        ej = float(r[elec]) if pd.notna(r[elec]) else 0.0
        hj = float(r[dh]) if dh and pd.notna(r[dh]) else 0.0
        cj = float(r[dc]) if dc and pd.notna(r[dc]) else 0.0
        # skip empty meter rows (common between environments)
        if ej == 0.0 and hj == 0.0 and cj == 0.0:
            # keep zeros during low-load hours — but drop if entire row NaN originally
            if dh and pd.isna(r[elec]) and (dh is None or pd.isna(r[dh])):
                continue
        parts = site_electric_proxy_kw(
            ej,
            hj,
            cj,
            interval_hours=interval_hours,
            heat_cop=heat_cop,
            cool_cop=cool_cop,
        )
        kw = parts["site_electric_proxy_kw"]
        if not pd.isna(kw) and abs(kw) < 1e6:  # drop absurd sizing spikes
            rows.append(
                {
                    "eplus_stamp": stamp,
                    "electricity_j": ej,
                    "district_heating_j": hj,
                    "district_cooling_j": cj,
                    **parts,
                }
            )
    out = pd.DataFrame(rows)
    out.attrs["source_csv"] = str(src)
    out.attrs["interval_hours"] = interval_hours
    out.attrs["elec_col"] = elec
    return out


def filter_stamps_for_day(df: pd.DataFrame, day_iso: str) -> pd.DataFrame:
    """Keep rows whose E+ stamp month/day matches ``YYYY-MM-DD`` (drops design days)."""
    y, m, d = [int(x) for x in day_iso.split("-")]
    keep = []
    for stamp in df["eplus_stamp"].astype(str):
        try:
            mm = int(stamp.split("/")[0].strip())
            dd = int(stamp.split("/")[1].split()[0])
            keep.append(mm == m and dd == d)
        except Exception:
            keep.append(False)
    return df.loc[keep].reset_index(drop=True)


def to_hourly_mean_kw(timestep_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate timestep proxy kW to hourly mean (4× 15-min → 1h) by stamp hour."""
    if timestep_df.empty:
        return timestep_df
    df = timestep_df.copy()

    def hour_key(stamp: str) -> str:
        # "01/05  14:15:00" → "01/05 14"
        parts = str(stamp).strip().split()
        if len(parts) < 2:
            return stamp
        hm = parts[1].split(":")
        h = int(hm[0])
        if h == 24:
            # fold into hour 0 next day label still ok for grouping energy
            h = 0
        return f"{parts[0]} {h:02d}"

    df["hour_key"] = df["eplus_stamp"].map(hour_key)
    g = df.groupby("hour_key", as_index=False).agg(
        site_electric_proxy_kw=("site_electric_proxy_kw", "mean"),
        site_electric_proxy_kwh=("site_electric_proxy_kwh", "sum"),
        eplus_stamp=("eplus_stamp", "last"),
    )
    return g
