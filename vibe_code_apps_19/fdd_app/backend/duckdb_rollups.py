"""DuckDB rollups on Feather/Parquet historian sidecars — zone/plant analytics."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

_HERE = Path(__file__).resolve().parent
_FEATHER_DIR = _HERE / ".cache" / "feather"


def _duckdb_available() -> bool:
    try:
        import duckdb  # noqa: F401
        return True
    except ImportError:
        return False


def _feather_files() -> list[Path]:
    if not _FEATHER_DIR.is_dir():
        return []
    return sorted(_FEATHER_DIR.glob("*.feather"))


def zone_comfort_pct_from_feather(
    zone_cols: list[str],
    *,
    lo: float = 68.0,
    hi: float = 76.0,
    feather_path: Path | None = None,
) -> float | None:
    """Compute % of zone temp samples in comfort band via DuckDB on one feather file."""
    if not _duckdb_available() or not zone_cols:
        return None
    import duckdb

    paths = [feather_path] if feather_path else _feather_files()
    if not paths:
        return None

    # Use first AHU-scale feather that has zone columns
    for path in paths:
        try:
            cols_sql = ", ".join(f'"{c}"' for c in zone_cols if c)
            if not cols_sql:
                continue
            q = f"""
            SELECT AVG(in_band) * 100.0 AS pct
            FROM (
              SELECT CASE WHEN (
                {" OR ".join(f'("{c}" >= {lo} AND "{c}" <= {hi})' for c in zone_cols)}
              ) THEN 1.0 ELSE 0.0 END AS in_band
              FROM read_feather('{path.as_posix()}')
            ) t
            """
            row = duckdb.sql(q).fetchone()
            if row and row[0] is not None:
                return round(float(row[0]), 2)
        except Exception:
            continue
    return None


def weekly_mean_from_feather(
    path: Path,
    column: str,
    *,
    ts_col: str = "timestamp",
) -> pd.DataFrame | None:
    """Weekly mean of one column via DuckDB."""
    if not _duckdb_available() or not path.is_file():
        return None
    import duckdb

    try:
        q = f"""
        SELECT date_trunc('week', "{ts_col}") AS week_start,
               avg("{column}") AS mean_val
        FROM read_feather('{path.as_posix()}')
        WHERE "{column}" IS NOT NULL
        GROUP BY 1
        ORDER BY 1
        """
        return duckdb.sql(q).df()
    except Exception:
        return None


def chiller_oat_bin_hours(
    plant: dict,
    wx: pd.DataFrame,
    *,
    oat_col: str = "dry_bulb_f",
    bin_width: float = 5.0,
    poll_seconds: float = 300.0,
) -> pd.DataFrame:
    """Chiller pump-on hours binned by OAT — DuckDB when available, else pandas."""
    import numpy as np

    wx = wx[["timestamp", oat_col]].copy()
    wx["oat"] = pd.to_numeric(wx[oat_col], errors="coerce")
    wx["bin_start"] = (np.floor(wx["oat"].clip(40, 110) / bin_width) * bin_width).astype("Int64")

    rows = []
    for key, label in [("CHILLER_1", "Chiller 1"), ("CHILLER_2", "Chiller 2")]:
        if key not in plant:
            continue
        d = plant[key][["timestamp", "pump_on"]].merge(wx[["timestamp", "bin_start"]], on="timestamp", how="inner")
        on = d[d["pump_on"].fillna(False)]
        if _duckdb_available() and not on.empty:
            import duckdb
            try:
                con = duckdb.connect()
                con.register("on", on)
                q = f"""
                SELECT bin_start, count(*) * {poll_seconds} / 3600.0 AS hours
                FROM on
                WHERE bin_start IS NOT NULL
                GROUP BY 1 ORDER BY 1
                """
                for _, r in con.sql(q).df().iterrows():
                    bs = int(r["bin_start"])
                    rows.append({
                        "bin_start": bs,
                        "bin_label": f"{bs}-{bs + int(bin_width) - 1}",
                        "source": label,
                        "hours": round(float(r["hours"]), 2),
                    })
                continue
            except Exception:
                pass
        for bin_start, g in on.groupby("bin_start"):
            if pd.isna(bin_start):
                continue
            rows.append({
                "bin_start": int(bin_start),
                "bin_label": f"{int(bin_start)}-{int(bin_start) + int(bin_width) - 1}",
                "source": label,
                "hours": round(len(g) * poll_seconds / 3600.0, 2),
            })
    return pd.DataFrame(rows).sort_values(["source", "bin_start"]) if rows else pd.DataFrame()


def oat_bin_hours(
    wx_df: pd.DataFrame,
    *,
    oat_col: str = "dry_bulb_f",
    bin_width: float = 5.0,
    poll_seconds: float = 300.0,
) -> pd.DataFrame:
    """OAT bin hour counts — DuckDB if available, else pandas."""
    if wx_df is None or wx_df.empty or oat_col not in wx_df.columns:
        return pd.DataFrame()

    if _duckdb_available():
        import duckdb
        try:
            con = duckdb.connect()
            con.register("wx", wx_df)
            q = f"""
            SELECT floor("{oat_col}" / {bin_width}) * {bin_width} AS oat_bin,
                   count(*) * {poll_seconds} / 3600.0 AS hours
            FROM wx
            WHERE "{oat_col}" IS NOT NULL
            GROUP BY 1
            ORDER BY 1
            """
            return con.sql(q).df()
        except Exception:
            pass

    s = pd.to_numeric(wx_df[oat_col], errors="coerce").dropna()
    bins = (s // bin_width) * bin_width
    counts = bins.value_counts().sort_index()
    hours = counts * poll_seconds / 3600.0
    return pd.DataFrame({"oat_bin": hours.index, "hours": hours.values})
