"""Extract IdealLoads+COP site electric proxy and zone MAT from eplusout/eplusmtr CSV."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from eplus_native.align import parse_eplus_csv_timestamp
from eplus_native.idf_stage import DSM_ZONES
from eplus_native.meters import site_electric_proxy_kw

# Short column names used by ML / farm parquet
ZONE_TEMP_COLS = {
    "1F_Area_A": "zone_temp_1F_A_f",
    "1F_Area_B": "zone_temp_1F_B_f",
    "1F_Area_C": "zone_temp_1F_C_f",
    "1F_Area_D": "zone_temp_1F_D_f",
    "2F_Area_A": "zone_temp_2F_A_f",
    "2F_Area_B": "zone_temp_2F_B_f",
}


def _find_col(columns: list[str], *needles: str) -> str | None:
    low = {c: c.lower() for c in columns}
    for c, lc in low.items():
        if all(n.lower() in lc for n in needles):
            return c
    return None


def _c_to_f(c: float) -> float:
    return float(c) * 9.0 / 5.0 + 32.0


def _find_zone_mat_col(columns: list[str], zone: str, *, prefer_freq: str = "timestep") -> str | None:
    """Match ``ZONE:Zone Mean Air Temperature … (TimeStep)`` case-insensitively."""
    z_l = zone.lower()
    candidates: list[str] = []
    for c in columns:
        cl = c.lower()
        if z_l not in cl:
            continue
        if "mean air temperature" not in cl:
            continue
        if "monthly" in cl or "daily" in cl:
            continue
        candidates.append(c)
    if not candidates:
        return None
    freq = prefer_freq.lower()
    if freq == "timestep":
        for c in candidates:
            if "timestep" in c.lower() or "time step" in c.lower():
                return c
    for c in candidates:
        if "hourly" not in c.lower():
            return c
    return candidates[0]


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


def load_timestep_zone_mat_f(
    sim_dir: Path | str,
    *,
    zones: tuple[str, ...] = DSM_ZONES,
    prefer_freq: str = "timestep",
) -> pd.DataFrame:
    """Timestep Zone Mean Air Temperature (°F) for DSM areas from eplusout.csv."""
    sim = Path(sim_dir)
    src = sim / "eplusout.csv"
    if not src.is_file():
        raise FileNotFoundError(f"missing {src}")
    df = pd.read_csv(src)
    cols = list(df.columns)
    ts_col = cols[0]
    zone_cols: dict[str, str] = {}
    missing = []
    for z in zones:
        c = _find_zone_mat_col(cols, z, prefer_freq=prefer_freq)
        if c is None:
            missing.append(z)
        else:
            zone_cols[z] = c
    if missing:
        raise ValueError(
            f"Zone Mean Air Temperature columns missing for {missing} in {src.name}. "
            "Ensure Output:Variable Zone Mean Air Temperature Timestep is in the run IDF."
        )

    rows = []
    for _, r in df.iterrows():
        stamp = str(r[ts_col]).strip()
        if not stamp or stamp.lower().startswith("date"):
            continue
        rec: dict = {"eplus_stamp": stamp}
        ok = True
        for z, c in zone_cols.items():
            if pd.isna(r[c]):
                ok = False
                break
            rec[ZONE_TEMP_COLS[z]] = _c_to_f(float(r[c]))
        if ok:
            rows.append(rec)
    out = pd.DataFrame(rows)
    out.attrs["source_csv"] = str(src)
    out.attrs["zone_cols"] = zone_cols
    return out


def load_timestep_proxy_and_mat(
    sim_dir: Path | str,
    *,
    heat_cop: float = 3.5,
    cool_cop: float = 4.5,
    interval_hours: float = 0.25,
    zones: tuple[str, ...] = DSM_ZONES,
) -> pd.DataFrame:
    """Join facility IdealLoads+COP proxy kW with 6-area MAT (°F) on eplus_stamp."""
    kw = load_timestep_proxy_kw(
        sim_dir,
        heat_cop=heat_cop,
        cool_cop=cool_cop,
        interval_hours=interval_hours,
    )
    mat = load_timestep_zone_mat_f(sim_dir, zones=zones)
    # Deduplicate stamp collisions (keep last)
    kw = kw.drop_duplicates(subset=["eplus_stamp"], keep="last")
    mat = mat.drop_duplicates(subset=["eplus_stamp"], keep="last")
    merged = kw.merge(mat, on="eplus_stamp", how="inner")
    if merged.empty:
        raise ValueError("proxy/MAT join produced empty frame (stamp mismatch)")
    return merged


def attach_utc_timestamps(
    df: pd.DataFrame,
    *,
    year_hint: int,
    stamp_col: str = "eplus_stamp",
) -> pd.DataFrame:
    """Add timestamp_utc from E+ stamps (fixed CST−6 → UTC)."""
    from datetime import timezone as _tz

    out = df.copy()
    dts = [parse_eplus_csv_timestamp(s, year_hint=year_hint) for s in out[stamp_col].astype(str)]
    out["timestamp_utc"] = [
        d.astimezone(_tz.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if d is not None else None for d in dts
    ]
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
    agg: dict = {
        "site_electric_proxy_kw": ("site_electric_proxy_kw", "mean"),
        "site_electric_proxy_kwh": ("site_electric_proxy_kwh", "sum"),
        "eplus_stamp": ("eplus_stamp", "last"),
    }
    for col in ZONE_TEMP_COLS.values():
        if col in df.columns:
            agg[col] = (col, "mean")
    g = df.groupby("hour_key", as_index=False).agg(**{k: v for k, v in agg.items()})
    return g


def interval_ending_local(stamp: str) -> tuple[int, int, int]:
    """Return (hour_ending_1_24, minute, quarter_index_0_95) from E+ stamp.

    Delegates to ``interval15.from_eplus_stamp`` so farm and extract agree.
    """
    try:
        from interval15 import from_eplus_stamp
    except ImportError:  # pragma: no cover
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ml"))
        from interval15 import from_eplus_stamp
    return from_eplus_stamp(stamp)
