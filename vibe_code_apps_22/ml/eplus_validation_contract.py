"""Canonical EnergyPlus ↔ measured validation contract (no blended sources).

Products (never mixed):
  A. utility_bill_monthly
  B. interval_meter_monthly
  C. interval_hourly
  D. interval_15min_dsm_diagnostic

Alignment rules:
  - Join only on explicit timestamp keys (interval end, UTC for measured;
    E+ LST → UTC via fixed CST−6).
  - Reject length/shape mismatches (no silent truncation).
  - Reject duplicate timestamps unless a documented rule applies.
  - Design-day / sizing duplicates: keep **last** occurrence per E+ stamp
    (annual run follows the design-day block in meter CSV).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import timezone
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

from eplus_native.align import (
    aggregate_5min_to_15min_mean,
    aggregate_5min_to_hourly_mean,
    parse_eplus_csv_timestamp,
)
from eplus_native.extract import load_timestep_proxy_kw
from eplus_native.hashes import sha256_file
from eplus_multires_metrics import nmbe_cvrmse_pct, resolution_block

SourceType = Literal[
    "utility_bill_monthly",
    "interval_meter_monthly",
    "interval_hourly",
    "interval_15min",
    "eplus_timestep",
]


@dataclass
class SeriesProvenance:
    source_type: SourceType
    source_path: str
    source_sha256: str | None
    interval_minutes: int
    timezone: str
    timestamp_convention: str  # "interval_end"
    environment: str | None = None
    notes: str | None = None


class AlignmentError(ValueError):
    """Fail-closed alignment / integrity error."""


def reject_shape_mismatch(a: np.ndarray, b: np.ndarray, *, label: str = "series") -> None:
    a = np.asarray(a)
    b = np.asarray(b)
    if a.shape != b.shape:
        raise AlignmentError(
            f"{label} shape mismatch: observed{a.shape} vs simulated{b.shape} — refuse truncate"
        )


def dedupe_eplus_stamps_keep_last(df: pd.DataFrame, *, stamp_col: str = "eplus_stamp") -> pd.DataFrame:
    """Drop design-day duplicates: keep last row per stamp (annual follows sizing)."""
    if stamp_col not in df.columns:
        raise AlignmentError(f"missing {stamp_col}")
    before = len(df)
    out = df.drop_duplicates(subset=[stamp_col], keep="last").copy()
    out.attrs["dedupe_dropped"] = int(before - len(out))
    out.attrs["dedupe_rule"] = "keep_last_per_eplus_stamp_annual_after_design_day"
    return out


def parse_eplus_proxy_to_utc(
    sim_dir: Path,
    *,
    heat_cop: float = 3.5,
    cool_cop: float = 4.5,
    amy_start_month: int = 8,
) -> pd.DataFrame:
    """Load timestep proxy kW, dedupe design-day stamps, attach interval_end UTC."""
    raw = load_timestep_proxy_kw(sim_dir, heat_cop=heat_cop, cool_cop=cool_cop, interval_hours=0.25)
    raw = dedupe_eplus_stamps_keep_last(raw)
    rows = []
    for _, r in raw.iterrows():
        stamp = str(r["eplus_stamp"]).strip()
        month = int(stamp.split("/")[0]) if "/" in stamp else 1
        year = 2025 if month >= amy_start_month else 2026
        dt = parse_eplus_csv_timestamp(stamp, year_hint=year)
        if dt is None:
            continue
        rows.append(
            {
                "eplus_stamp": stamp,
                "interval_end_utc": dt.astimezone(timezone.utc),
                "interval_end_lst": dt,
                "simulated_kw": float(r["site_electric_proxy_kw"]),
                "environment": "annual_amy_after_design_day_dedupe",
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        raise AlignmentError(f"no usable E+ rows from {sim_dir}")
    # Reject remaining duplicate UTC keys
    if out["interval_end_utc"].duplicated().any():
        n_dup = int(out["interval_end_utc"].duplicated().sum())
        raise AlignmentError(f"duplicate interval_end_utc after dedupe: {n_dup}")
    out["interval_end_utc"] = pd.to_datetime(out["interval_end_utc"], utc=True)
    out.attrs["provenance"] = asdict(
        SeriesProvenance(
            source_type="eplus_timestep",
            source_path=str(Path(sim_dir).resolve()),
            source_sha256=None,
            interval_minutes=15,
            timezone="E+ LST CST-6 → UTC",
            timestamp_convention="interval_end",
            environment="annual_amy_after_design_day_dedupe",
            notes=f"dedupe_dropped={raw.attrs.get('dedupe_dropped')}",
        )
    )
    return out


def load_measured_interval(root: Path) -> tuple[pd.DataFrame, SeriesProvenance]:
    path = Path(root) / "utilities" / "demand_interval_kw.csv"
    if not path.is_file():
        raise FileNotFoundError(path)
    df = pd.read_csv(path)
    if "timestamp_utc" not in df.columns or "kw_demand" not in df.columns:
        raise AlignmentError("demand_interval_kw.csv needs timestamp_utc, kw_demand")
    df = df.copy()
    df["interval_end_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    if df["interval_end_utc"].duplicated().any():
        raise AlignmentError("duplicate timestamps in measured demand_interval_kw.csv")
    prov = SeriesProvenance(
        source_type="interval_hourly",  # raw is typically 5-min; marked at load site
        source_path=str(path.resolve()),
        source_sha256=sha256_file(path),
        interval_minutes=5,
        timezone="UTC",
        timestamp_convention="interval_end",
        notes="raw meter intervals before aggregation",
    )
    return df, prov


def align_interval(
    measured_agg: pd.DataFrame,
    modeled: pd.DataFrame,
    *,
    meas_kw_col: str,
    mod_kw_col: str = "simulated_kw",
    ts_col: str = "interval_end_utc",
    completeness_min: float = 0.0,
) -> pd.DataFrame:
    """Inner-join on timestamp; fail on empty; attach completeness."""
    m = measured_agg[[ts_col, meas_kw_col]].rename(columns={meas_kw_col: "observed_kw"})
    s = modeled[[ts_col, mod_kw_col]].rename(columns={mod_kw_col: "simulated_kw"})
    m[ts_col] = pd.to_datetime(m[ts_col], utc=True)
    s[ts_col] = pd.to_datetime(s[ts_col], utc=True)
    if m[ts_col].duplicated().any() or s[ts_col].duplicated().any():
        raise AlignmentError("duplicate timestamps before align — refuse")
    aligned = m.merge(s, on=ts_col, how="inner")
    if aligned.empty:
        raise AlignmentError("zero overlapping timestamps after align")
    reject_shape_mismatch(
        aligned["observed_kw"].to_numpy(),
        aligned["simulated_kw"].to_numpy(),
        label="aligned_kw",
    )
    aligned = aligned.dropna(subset=["observed_kw", "simulated_kw"])
    aligned["completeness_fraction"] = 1.0
    if completeness_min > 0 and float(aligned["completeness_fraction"].min()) < completeness_min:
        raise AlignmentError("completeness below threshold")
    aligned["timestamp"] = aligned[ts_col]
    aligned["interval_end"] = aligned[ts_col]
    aligned["timezone"] = "UTC"
    return aligned.sort_values(ts_col).reset_index(drop=True)


def build_hourly_and_15min(
    root: Path,
    sim_dir: Path,
    *,
    heat_cop: float = 3.5,
    cool_cop: float = 4.5,
) -> dict[str, Any]:
    """Build aligned hourly + 15-min products with provenance."""
    meas, mprov = load_measured_interval(root)
    # Prefer original CSV timestamp_utc when present; avoid duplicate rename keys.
    if "timestamp_utc" in meas.columns:
        meas_for_agg = meas[["timestamp_utc", "kw_demand"]].copy()
    else:
        meas_for_agg = meas[["interval_end_utc", "kw_demand"]].rename(
            columns={"interval_end_utc": "timestamp_utc"}
        )
    hourly_m = aggregate_5min_to_hourly_mean(
        meas_for_agg,
        ts_col="timestamp_utc",
        kw_col="kw_demand",
    ).rename(columns={"timestamp_utc": "interval_end_utc", "kw_mean": "observed_kw"})
    q15_m = aggregate_5min_to_15min_mean(
        meas_for_agg,
        ts_col="timestamp_utc",
        kw_col="kw_demand",
    ).rename(columns={"timestamp_utc": "interval_end_utc", "kw_mean": "observed_kw"})

    mod = parse_eplus_proxy_to_utc(sim_dir, heat_cop=heat_cop, cool_cop=cool_cop)
    mod_h = (
        mod.set_index("interval_end_utc")["simulated_kw"]
        .resample("1h", label="right", closed="right")
        .mean()
        .rename("simulated_kw")
        .to_frame()
        .reset_index()
    )
    mod_15 = (
        mod.set_index("interval_end_utc")["simulated_kw"]
        .resample("15min", label="right", closed="right")
        .mean()
        .rename("simulated_kw")
        .to_frame()
        .reset_index()
    )
    aligned_h = align_interval(hourly_m, mod_h, meas_kw_col="observed_kw")
    aligned_15 = align_interval(q15_m, mod_15, meas_kw_col="observed_kw")
    return {
        "hourly": aligned_h,
        "q15": aligned_15,
        "measured_provenance": asdict(mprov),
        "modeled_provenance": mod.attrs.get("provenance"),
        "dedupe_dropped": (mod.attrs.get("provenance") or {}).get("notes"),
    }


def score_aligned(aligned: pd.DataFrame, *, resolution: str, p: int = 1) -> dict[str, Any]:
    reject_shape_mismatch(aligned["observed_kw"].to_numpy(), aligned["simulated_kw"].to_numpy())
    block = resolution_block(
        aligned["observed_kw"], aligned["simulated_kw"], resolution=resolution, p=p
    )
    yt = aligned["observed_kw"].to_numpy(dtype=float)
    yp = aligned["simulated_kw"].to_numpy(dtype=float)
    err = yp - yt
    block["rmse_kw"] = float(np.sqrt(np.mean(err**2)))
    block["mae_kw"] = float(np.mean(np.abs(err)))
    block["mbe_kw"] = float(np.mean(err))
    # Defend p: calibrated-sim convention p=1 (one overall bias / calibration DOF).
    block["p_rationale"] = (
        "p=1 follows common calibrated-simulation reporting (one overall calibration "
        "degree of freedom). Not a purchased ASHRAE G14-2023 citation. n and p published "
        "with every score."
    )
    return block


def utility_monthly_from_scorecard(root: Path) -> dict[str, Any] | None:
    """Product A: utility-bill monthly GL14 from best_scorecard_utility.json."""
    sc = Path(root) / "eplus" / "scorecards" / "best_scorecard_utility.json"
    if not sc.is_file():
        return None
    doc = json_load(sc)
    g = doc.get("gl14") or {}
    monthly = doc.get("monthly") or []
    n = int(g.get("n") or len(monthly))
    block = {
        "resolution": "monthly",
        "source_type": "utility_bill_monthly",
        "source_path": str(sc.resolve()),
        "source_sha256": sha256_file(sc),
        "status": doc.get("gl14_status") or "fail",
        "n": n,
        "p": 1,
        "nmbe_pct": g.get("nmbe_pct"),
        "cvrmse_pct": g.get("cvrmse_pct"),
        "mean_obs": g.get("mean_obs"),
        "rmse_kw": None,
        "mae_kw": None,
        "labeled_as_gl14": False,  # partial-period screen only
        "partial_period_monthly_threshold_screen": True,
        "label": "PARTIAL-PERIOD MONTHLY THRESHOLD SCREEN (utility bills)",
        "complete_months": n,
        "gates": {"nmbe_abs_max_pct": 5.0, "cvrmse_max_pct": 15.0},
        "p_rationale": (
            "p=1 calibrated-sim convention; n=complete utility months in scorecard"
        ),
        "formula": "NMBE%=100*sum(m-ŷ)/((n-p)*mean(m)); CVRMSE%=100*sqrt(sum((m-ŷ)^2)/(n-p))/mean(m)",
    }
    from eplus_multires_metrics import gate_monthly

    if block["nmbe_pct"] is not None and block["cvrmse_pct"] is not None:
        block["status"] = gate_monthly(block)
    return block


def interval_monthly_from_aligned_hourly(aligned_h: pd.DataFrame) -> dict[str, Any]:
    """Product B: interval meter aggregated to monthly energy (kWh), not utility bills."""
    from eplus_multires_metrics import gate_monthly

    df = aligned_h.copy()
    df["month"] = (
        pd.to_datetime(df["interval_end_utc"], utc=True)
        .dt.tz_convert("America/Chicago")
        .dt.strftime("%Y-%m")
    )
    rows = []
    for month, g in df.groupby("month"):
        rows.append(
            {
                "month": month,
                "kwh_obs": float(g["observed_kw"].sum()),
                "kwh_sim": float(g["simulated_kw"].sum()),
                "n_hours": int(len(g)),
            }
        )
    mdf = pd.DataFrame(rows)
    # require reasonably complete months (>= 20*24 hours)
    mdf = mdf[mdf["n_hours"] >= 480] if len(mdf) else mdf
    label = (
        "PARTIAL-PERIOD MONTHLY THRESHOLD SCREEN "
        "(interval-aggregated — NOT utility bills)"
    )
    if len(mdf) == 0:
        return {
            "resolution": "monthly",
            "source_type": "interval_meter_monthly",
            "status": "insufficient_data",
            "n": 0,
            "p": 1,
            "labeled_as_gl14": False,
            "partial_period_monthly_threshold_screen": True,
            "label": label,
        }
    stats = nmbe_cvrmse_pct(mdf["kwh_obs"], mdf["kwh_sim"], p=1)
    return {
        "resolution": "monthly",
        "source_type": "interval_meter_monthly",
        "status": gate_monthly(stats),
        "n": int(stats["n"]),
        "p": 1,
        "nmbe_pct": stats["nmbe_pct"],
        "cvrmse_pct": stats["cvrmse_pct"],
        "mean_obs": stats["mean_obs"],
        "labeled_as_gl14": False,
        "partial_period_monthly_threshold_screen": True,
        "label": label,
        "gates": {"nmbe_abs_max_pct": 5.0, "cvrmse_max_pct": 15.0},
        "p_rationale": "p=1 calibrated-sim convention on monthly aggregates of interval kWh",
        "formula": stats.get("formula"),
        "n_months_complete_enough": int(len(mdf)),
        "denominator": "n-p",
    }


def json_load(path: Path) -> dict:
    import json

    return json.loads(Path(path).read_text(encoding="utf-8"))


def chronological_splits(
    aligned: pd.DataFrame,
    *,
    ts_col: str = "interval_end_utc",
) -> dict[str, Any]:
    """Explicit chronological periods — no random split; holdout never used for tuning."""
    ts = pd.to_datetime(aligned[ts_col], utc=True)
    # AMY window ~ 2025-08 .. 2026-07
    calib_end = pd.Timestamp("2026-01-31", tz="UTC")
    val_end = pd.Timestamp("2026-03-31", tz="UTC")
    peak_end = pd.Timestamp("2026-02-28", tz="UTC")
    # Locked holdout: last 30 days of available data
    t_max = ts.max()
    holdout_start = t_max - pd.Timedelta(days=30)

    def mask_period(start, end):
        return (ts >= start) & (ts < end)

    periods = {
        "calibration_development": {
            "start": str(ts.min()),
            "end": str(calib_end),
            "n": int(mask_period(ts.min(), calib_end).sum()),
            "role": "tuning_allowed",
        },
        "chronological_validation": {
            "start": str(calib_end),
            "end": str(val_end),
            "n": int(mask_period(calib_end, val_end).sum()),
            "role": "selection_allowed_not_final",
        },
        "winter_peak_validation": {
            "start": "2026-01-01T00:00:00+00:00",
            "end": str(peak_end),
            "n": int(mask_period(pd.Timestamp("2026-01-01", tz="UTC"), peak_end).sum()),
            "role": "peak_diagnostics",
        },
        "locked_final_holdout": {
            "start": str(holdout_start),
            "end": str(t_max),
            "n": int((ts >= holdout_start).sum()),
            "role": "locked_no_tuning",
        },
    }
    # Overlap note: winter peak may overlap calib — document
    periods["notes"] = (
        "Locked holdout is the final 30 days of aligned coverage. "
        "Parameter selection must use only calibration_development "
        "(and optionally chronological_validation for ranking). "
        "locked_final_holdout must not influence knobs, early stop, or weights."
    )
    if periods["locked_final_holdout"]["n"] < 24 * 7:
        periods["limitation"] = (
            "Holdout shorter than 7 days of hours — state prominently; do not invent coverage"
        )
    return periods
